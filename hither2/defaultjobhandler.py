from ._basejobhandler import BaseJobHandler
from ._enums import JobStatus

class DefaultJobHandler(BaseJobHandler):
    def __init__(self):
        self.is_remote = False

    def handle_job(self, job):
        # superclass implementation does standard logging and universal job status update
        super(DefaultJobHandler, self).handle_job(job)
        job._execute()

    def cancel_job(self, job_id):
        print('Warning: not yet able to cancel job of defaultjobhandler')

    def iterate(self):
        pass
