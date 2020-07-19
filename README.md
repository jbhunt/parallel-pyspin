# Description #
This package provides another layer of abstraction around the PySpin package. It provides two major improvements.

1.) Parallel operation of cameras via the multiprocessing package.

2.) Built-in/automatic primary and secondary camera configuration.

# Installation #
TODO : Document the installation procedure.

# Examples #

Here is an example which demonstrates the functionality of the parallel_pyspin.stream.VideoCapture class  OpenCV's VideoCapture object.

```python
>>> from parallel_pyspin.stream import VideoCapture
>>> cap = VideoCapture(0) # 0 is device index
>>> cap.isOpened()
True
>>> result,image = cap.read()
>>> result
True
>>> image.shape
(540,720)
>>> cap.release()
```
