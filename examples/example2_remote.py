#!/usr/bin/env python

import os
import numpy as np
import hither2 as hi
import time

@hi.function('sumsqr', '0.1.0')
@hi.container('docker://jupyter/scipy-notebook:latest')
def sumsqr(x):
    return np.sum(x**2)

@hi.function('sumsqr_with_delay', '0.1.0')
@hi.container('docker://jupyter/scipy-notebook:latest')
def sumsqr_with_delay(x, delay: float):
    print('sumsqr_with_delay 1')
    time.sleep(delay)
    print('sumsqr_with_delay 2')
    return np.sum(x**2)

@hi.function('addone', '0.1.0')
def addone(x):
    return x + 1

@hi.function('addem', '0.1.0')
@hi.container('docker://jupyter/scipy-notebook:latest')
def addem(x):
    return np.sum(x)

def main():
    mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    db = hi.Database(mongo_url=mongo_url, database='hither2')
    with hi.config(job_handler=hi.RemoteJobHandler(database=db, compute_resource_id='resource1'), container=True):
        delay = 15
        val1 = sumsqr_with_delay.run(x=np.array([1]), delay=delay)
        val2 = sumsqr_with_delay.run(x=np.array([1,2]), delay=delay)
        val3 = sumsqr_with_delay.run(x=np.array([1,2,3]), delay=delay)
        val4 = addem.run(x=[val1, val2, val3])
        print(val1.wait(), val2.wait(), val3.wait(), val4.wait())
        assert val1.wait() == 1
        assert val2.wait() == 5
        assert val3.wait() == 14
        assert val4.wait() == 20

if __name__ == '__main__':
    main()