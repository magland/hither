import os
import sys
from typing import Any, List, Tuple, Union, Dict
import json
import shutil
import time
from ._temporarydirectory import TemporaryDirectory
from ._shellscript import ShellScript
import kachery as ka
from ._util import _docker_form_of_container_string, _random_string
from ._util import _deserialize_item, _serialize_item

def _run_serialized_job_in_container(job_serialized):
    name = job_serialized['function_name']
    version = job_serialized['function_version']
    label = job_serialized['label']
    if label is None:
        label = name
    show_console = True
    gpu = False
    # This variable is reserved for future use
    timeout: Union[None, float] = None
    
    code = job_serialized['code']
    container = job_serialized['container']
    no_resolve_input_files = job_serialized['no_resolve_input_files']

    kwargs = job_serialized['kwargs']

    remove = True
    if os.getenv('HITHER_DEBUG', None) == 'TRUE':
        remove = False
    with TemporaryDirectory(prefix='tmp_hither2_run_in_container_' + name + '_', remove=remove) as temp_path:
        _write_python_code_to_directory(os.path.join(temp_path, 'function_src'), code)
        
        if container is not None:
            run_in_container_path = '/run_in_container'
            env_vars_inside_container = dict(
                KACHERY_STORAGE_DIR='/kachery-storage',
                PYTHONPATH=f'{run_in_container_path}/function_src/_local_modules',
                HOME='$HOME'
            )
        else:
            run_in_container_path = temp_path
            env_vars_inside_container = dict(
                PYTHONPATH=f'{run_in_container_path}/function_src/_local_modules'
            )

        run_py_script = """
            #!/usr/bin/env python

            import sys
            import json
            import traceback

            def main():
                try:
                    import hither2
                    ok_import_hither2 = True
                except Exception as e:
                    traceback.print_exc()
                    retval = None
                    success = False
                    error = str(e)
                    runtime_info = dict()
                    ok_import_hither2 = False

                if ok_import_hither2:
                    from hither2 import ConsoleCapture
                    from hither2 import _deserialize_item, _serialize_item, _copy_structure_with_changes
                    from hither2 import File

                    kwargs = json.loads('{kwargs_json}')
                    kwargs = _deserialize_item(kwargs)
                    with ConsoleCapture(label='{label}', show_console={show_console_str}) as cc:
                        print('###### RUNNING: {label}')
                        try:
                            from function_src import {function_name}
                            if not {no_resolve_input_files}:
                                kwargs = _copy_structure_with_changes(kwargs,
                                    lambda arg: arg.resolve(), _type = File)
                            retval = {function_name}(**kwargs)
                            retval = _copy_structure_with_changes(retval, File.kache_numpy_array)
                            success = True
                            error = None
                        except Exception as e:
                            traceback.print_exc()
                            retval = None
                            success = False
                            error = str(e)
                    
                    retval = _serialize_item(retval)
                    
                    runtime_info = cc.runtime_info()
                result = dict(
                    retval=retval,
                    success=success,
                    runtime_info=runtime_info,
                    error=error
                )
                with open('{run_in_container_path}/result.json', 'w') as f:
                    json.dump(result, f)

            if __name__ == "__main__":
                try:
                    main()
                except:
                    sys.stdout.flush()
                    sys.stderr.flush()
                    raise
        """.format(
            kwargs_json=json.dumps(kwargs),
            function_name=name,
            label=label,
            show_console_str='True' if show_console else 'False',
            run_in_container_path=run_in_container_path,
            no_resolve_input_files='True' if no_resolve_input_files else 'False'
        )

        # For unindenting
        ShellScript(run_py_script).write(os.path.join(temp_path, 'run.py'))

        # See: https://wiki.bash-hackers.org/commands/builtin/exec
        run_inside_container_script = """
            #!/bin/bash
            set -e

            export NUM_WORKERS={num_workers_env}
            export MKL_NUM_THREADS=$NUM_WORKERS
            export NUMEXPR_NUM_THREADS=$NUM_WORKERS
            export OMP_NUM_THREADS=$NUM_WORKERS

            export {env_vars_inside_container}
            exec python3 {run_in_container_path}/run.py >> /tmp/debug_log.txt 2>> /tmp/debug_log_err.txt
        """.format(
            env_vars_inside_container=' '.join(['{}={}'.format(k, v) for k, v in env_vars_inside_container.items()]),
            num_workers_env=os.getenv('NUM_WORKERS', ''),
            run_in_container_path=run_in_container_path
        )

        ShellScript(run_inside_container_script).write(os.path.join(temp_path, 'run.sh'))

        if not os.getenv('KACHERY_STORAGE_DIR'):
            raise Exception('You must set the environment variable: KACHERY_STORAGE_DIR')

        docker_container_name = None

        # fancy_command = 'bash -c "((bash /run_in_container/run.sh | tee /run_in_container/stdout.txt) 3>&1 1>&2 2>&3 | tee /run_in_container/stderr.txt) 3>&1 1>&2 1>&3 | tee /run_in_container/console_out.txt"'
        if container is None:
            run_outside_container_script = """
                #!/bin/bash

                exec {run_in_container_path}/run.sh
            """.format(
                run_in_container_path=run_in_container_path
            )
        elif os.getenv('HITHER_USE_SINGULARITY', None) == 'TRUE':
            if gpu:
                gpu_opt = '--nv'
            else:
                gpu_opt = ''
            run_outside_container_script = """
                #!/bin/bash

                # {label} ({name} {version})

                exec singularity exec -e {gpu_opt} \\
                    -B $KACHERY_STORAGE_DIR:/kachery-storage \\
                    -B {temp_path}:/run_in_container \\
                    {container} \\
                    bash /run_in_container/run.sh
            """.format(
                gpu_opt=gpu_opt,
                container=container,
                temp_path=temp_path,
                label=label,
                name=name,
                version=version
            )
        else:
            if gpu:
                gpu_opt = '--gpus all'
            else:
                gpu_opt = ''
            docker_container_name = _random_string(8) + '_' + name
            # May not want to use -t below as it has the potential to mess up line feeds in the parent process!
            if (sys.platform == "win32"):
                if 1: # pragma: no cover
                    ## This win32 section needs to be updated!
                    winpath_ = lambda a : '/' + a.replace('\\','/').replace(':','')
                    container_ = _docker_form_of_container_string(container)
                    temp_path_ = winpath_(temp_path)
                    kachery_storage_dir_ = winpath_(os.getenv('KACHERY_STORAGE_DIR'))
                    print('temp_path_: ' + temp_path_)
                    run_outside_container_script = f'''
                        docker run --name {docker_container_name} -i {gpu_opt} ^
                        -v {kachery_storage_dir_}:/kachery-storage ^
                        -v {temp_path_}:/run_in_container ^
                        {container_} ^
                        bash /run_in_container/run.sh'''
            else:
                run_outside_container_script = """
                #!/bin/bash

                # {label} ({name} {version})

                exec docker run --name {docker_container_name} -i {gpu_opt} \\
                    -v /etc/localtime:/etc/localtime:ro \\
                    -v /etc/passwd:/etc/passwd -u `id -u`:`id -g` \\
                    -v $KACHERY_STORAGE_DIR:/kachery-storage \\
                    -v {temp_path}:/run_in_container \\
                    -v /tmp:/tmp \\
                    -v $HOME:$HOME \\
                    {container} \\
                    bash /run_in_container/run.sh
                """.format(
                    docker_container_name=docker_container_name,
                    gpu_opt=gpu_opt,
                    container=_docker_form_of_container_string(container),
                    temp_path=temp_path,
                    label=label,
                    name=name,
                    version=version
                )
        print('#############################################################')
        print(run_outside_container_script)
        print('#############################################################')

        try:
            ss = ShellScript(run_outside_container_script, keep_temp_files=False, label='run_outside_container', docker_container_name=docker_container_name)
            ss.start()
            timer = time.time()
            did_timeout = False
            while True:
                retcode = ss.wait(0.02)
                if retcode is not None:
                    break
                elapsed = time.time() - timer
                # TODO: this code is currently unreachable but should be uncommented when `timeout` is used.
                # if timeout is not None:
                #     if elapsed > timeout:
                #         print(f'Stopping job due to timeout {elapsed} > {timeout}')
                #         did_timeout = True
                #         ss.stop()
        finally:
            if docker_container_name is not None:
                ss_cleanup = ShellScript(f"""
                #!/bin/bash

                docker stop {docker_container_name} || true
                docker kill {docker_container_name} || true
                docker rm {docker_container_name} || true
                """)
                ss_cleanup.start()
                ss_cleanup.wait()

        # Need to think about the rest of this function
        if (retcode != 0) and (not did_timeout):
            # This is a genuine framework exception because if it were a function exception, we'd get that reported in the runtime_info
            raise Exception('Unexpected non-zero exit code ({}) running [{}] in container {}'.format(retcode, label, container))

        with open(os.path.join(temp_path, 'result.json')) as f:
            obj = json.load(f)
        retval = _deserialize_item(obj['retval'])
        runtime_info = obj['runtime_info']
        success = obj['success']
        error = obj['error']
        if not success:
            assert error is not None
            assert error != 'None'

        if did_timeout:
            runtime_info['timed_out'] = True
            success = False
        else:
            runtime_info['timed_out'] = False
        
        return success, retval, runtime_info, error

def _write_python_code_to_directory(dirname: str, code: dict) -> None:
    if os.path.exists(dirname):
        raise Exception(
            'Cannot write code to already existing directory: {}'.format(dirname))
    os.mkdir(dirname)
    for item in code['files']:
        fname0 = dirname + '/' + item['name']
        with open(fname0, 'w', newline='\n') as f:
            f.write(item['content'])
    for item in code['dirs']:
        _write_python_code_to_directory(
            dirname + '/' + item['name'], item['content'])
