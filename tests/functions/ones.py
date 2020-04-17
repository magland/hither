import hither2 as hi
import numpy as np

@hi.function('ones', '0.1.0')
@hi.container('docker://jupyter/scipy-notebook:678ada768ab1')
def ones(shape):
    return np.ones(shape=shape)

ones.test_calls = [
    dict(
        args=dict(
            shape=(2, 3, 4)
        ),
        result=np.ones((2, 3, 4))
    )
]