import os
import hither2 as hi
import numpy as np

@hi.function('additional_file', '0.1.0')
@hi.container('docker://jupyter/scipy-notebook:678ada768ab1')
@hi.additional_files(['test_data.csv'])
def additional_file():
    thisdir = os.path.dirname(os.path.realpath(__file__))
    a = np.loadtxt(thisdir + '/test_data.csv', delimiter=',')
    assert a.shape == (2, 3)
    return a

additional_file.test_calls = [
    dict(
        args=dict(),
        result=np.array([[1, 2, 3], [4, 5, 6]])
    )
]