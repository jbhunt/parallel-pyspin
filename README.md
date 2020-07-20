# Description #
This package provides another layer of abstraction on top of [PySpin](https://www.flir.com/products/spinnaker-sdk/) (the Python wrapper for FLIR's Spinnaker software development kit). This new layer of abstraction provides these additional features:

1.) Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package

2.) True synchronous video acquisition for multiple cameras

For questions or general correspondance please send an email to hunt.brian.joshua@gmail.com.

# Installation #
TODO : Document the installation procedure.

# Parallel camera operation #
TODO : Describe how multiprocessing is used to parallelize the camera operation

# Synchronous video acquisition #
TODO : Describe how the cameras are configured for simultaneous video acquisition

# Examples #
This example demonstrates the `parallel_pyspin.stream.VideoCapture` class which mimics [OpenCV's VideoCapture class](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html).

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
