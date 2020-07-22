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
## Streaming ##
### Creating a video stream ###
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

### Modifying video stream properties ###
You can modify a camera's framerate, exposure, or binsize using the VideoStream object's set method. In this example the exposure is changed from the default value (1500 us) to a new target value:

``` python
>>> from llpyspin import constants as c
>>> cap.get(c.CAP_PROP_EXPOSURE)
1500
>>> cap.set(c.CAP_PROP_EXPOSURE,3000) # this restarts the child process
>>> cap.get(c.CAP_PROP_EXPOSURE)
3000
```

## Recording ##
TODO : Add a description here.

### Basic primary camera use ###
```Python
>>> from llpyspin.cameras import PrimaryCamera
>>> device = str(12345678) # primary camera serial number
>>> cam = PrimaryCamera(device)
>>> cam.isPrimed() # check that the camera is primed
True
>>> cam.prime()
INFO : Video acquisition is already started
>>> cam.trigger() # trigger camera
>>> cam.stop() # stop acquisition
>>> cam.release() # release camera
>>> cam.isPrimed()
False
>>> cam.prime() # you can re-prime the camera for subsequent recordings
>>> cam.isPrimed()
True
```

### Modifying camera properties ###
Unlike the `llpyspin.stream.VideoStream` class which uses a class method to change acquisition properties, the `llpyspin.cameras.PrimaryCamera` class uses class properties to modify properties of the video acquisition. Valid properties are framerate, exposure, binsize, and mode (mode refers to the stream buffer handling mode).

```Python
>>> cam.framerate
120
>>> cam.framerate = 60 # this calls the private class method _set
WARNING : Failed to set framerate to 60 because acquisition is ongoing. # properties can't be set after the camera is primed
>>> cam.stop()
>>> cam.framerate = 60
>>> cam.framerate
60
>>> for attr in ['framerate','exposure','binsize','mode','foo']:
        print(hasattr(cam,attr))
True
True
True
True
False
```

### Setting up a secondary camera ###

# Acknowledgements #
Big thanks to Dr. Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.
