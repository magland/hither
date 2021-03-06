from collections import deque
from copy import deepcopy
from enum import Enum
from typing import Any, Deque, Dict, Union
from .jobcache import JobCache
from ._basejobhandler import BaseJobHandler

class Inherit(Enum):
    INHERIT = ''

class Config:
    config_stack: Deque[Dict[str, Any]] = deque()


    def __init__(self,
        container: Union[str, bool, Inherit, None]=Inherit.INHERIT,
        job_handler: Union[BaseJobHandler, Inherit]=Inherit.INHERIT,
        job_cache: Union[JobCache, Inherit, None]=Inherit.INHERIT,
        download_results: Union[bool, Inherit, None]=Inherit.INHERIT,
        job_timeout: Union[float, Inherit, None]=Inherit.INHERIT
    ):
        """Set hither2 config parameters in a context manager, inheriting unchanged parameters
        from the default config.

        Example usage:
        ```
        import hither2 as hi
        with hi.Config(container=True):
            # code goes here
        ```
        
        Parameters
        ----------
        container : Union[str, bool, None], optional
            If bool, controls whether to use the default docker container specified for each function job
            If str, use the docker container given by the string, by default None
        job_handler : Any, optional
            The job handler to use for each function job, by default None
        job_cache : Union[JobCache, None], optional
            The job cache to use for each function job, by default None
        download_results : Union[bool, None], optional
            Whether to download results after the function job runs (applied to remote job handler), by default None
        job_timeout : Union[float, None], optional
            A timeout time (in seconds) for each function job, by default None
        """
        old_config = Config.config_stack[-1] # throws if no default set
        self.new_config = dict()
        for k, v in old_config.items():
            # NOTE: per our typing, none of the objects are actually supposed to be dicts
            # but we had this in ETConf, so I'm keeping it around to be careful
            self.new_config[k] = deepcopy(v) if isinstance(v, dict) else v

        # TODO: find a neater way to do this (kwargs?)
        self.coalesce('container', container)
        self.coalesce('job_handler', job_handler)
        self.coalesce('job_cache', job_cache)
        self.coalesce('download_results', download_results)
        self.coalesce('job_timeout', job_timeout)


    @staticmethod
    # TODO: python 3.8 gives better tools for typehinting dicts, revise this eventually
    def set_default_config(cfg: Dict[Any, Any]) -> None:
        # TODO: Add a guard against resetting default config when one already exists?
        # There is probably a better way to handle the known-fields enumeration.
        known_fields = ['container', 'job_handler', 'job_cache', 'download_results', 'job_timeout']
        for k in known_fields:
            if k not in cfg:
                raise Exception(f"Proposed default configuration is missing a value for {k}")
            if cfg[k] == Inherit.INHERIT:
                raise Exception(f"Default configuration has no way to inherit the value of {k}.")
        Config.config_stack.clear()
        Config.config_stack.append(cfg)

    @staticmethod
    def get_current_config() -> Dict[str, Any]:
        return Config.config_stack[-1]

    @staticmethod
    def get_current_config_value(key: str) -> Any:
        d = Config.config_stack[-1]
        return d[key]

    def get_local_config(self) -> Dict[str, Any]:
        return self.new_config
    
    def get_local_config_value(self, key: str) -> Any:
        return self.new_config[key]

    def __enter__(self):
        Config.config_stack.append(self.new_config)
    def __exit__(self, exc_type, exc_val, exc_tb):
        Config.config_stack.pop()

    def coalesce(self, name: str, val: Any) -> None:
        if val == Inherit.INHERIT:
            return
        # This allows "None" to be passed as an actual value
        self.new_config[name] = val
