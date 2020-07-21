# Description #
This package provides another layer of abstraction on top of [PySpin](https://www.flir.com/products/spinnaker-sdk/) (the Python wrapper for FLIR's Spinnaker software development kit). This new layer of abstraction provides these additional features:

1.) Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package

2.) True synchronous video acquisition for multiple cameras

For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Installation #
TODO : Document the installation procedure.

# Parallel camera operation #
TODO : Describe how multiprocessing is used to parallelize the camera operation

# Synchronous video acquisition #
TODO : Describe how the cameras are configured for simultaneous video acquisition

# Examples #
## Creating a video stream ##
This example demonstrates how to use the `llpyspin.stream.VideoStream` class to create a video stream for a single camera. This class operates almost exactly like OpenCV's [VideoCapture](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html) class in that is has many of the same methods and functionality.

```python
>>> from llpyspin.stream import VideoStream
>>> device = 0 # device index
>>> cap = VideoStream(device)
>>> cap.isOpened()
True
>>> result,image = cap.read()
>>> result
True
>>> image.shape
(540,720)
>>> cap.release()
```

## Modifying acquisition properties ##
You can modify a camera's framerate, exposure, or binsize using the VideoStream object's set method. In this example the exposure is changed from the default value (1500 us) to a new target value:

``` python
>>> from llpyspin import constants
>>> cap.get(constants.CAP_PROP_EXPOSURE)
1500
>>> cap.set(constants.CAP_PROP_EXPOSURE,3000) # this restarts the child process - it will take a little bit of time
>>> cap.get(constants.CAP_PROP_EXPOSURE)
3000
```

# Acknowledgements #
Big thanks to Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.
