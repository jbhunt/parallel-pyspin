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
This example demonstrates how to use the `llpyspin.capture.VideoStream` class to create a video stream for a single camera. This class operates almost exactly like OpenCV's [VideoCapture](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html) class in that is has many of the same methods and functionality. Video streams are asynchronous.

```python
>>> from llpyspin.capture import VideoStream
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
You can modify a camera's framerate, exposure, or binsize using the stream's 'set' method. In this example the exposure is changed from the default value (1500 us) to a new target value. Supported capture properties are stored in the `llpyspin.constants` module. You can query the value of a capture property with the 'get' method.

``` python
>>> from llpyspin import constants as c
>>> cap.get(c.CAP_PROP_EXPOSURE)
1500
>>> cap.set(c.CAP_PROP_EXPOSURE,3000) # this restarts the child process
>>> cap.get(c.CAP_PROP_EXPOSURE)
3000
```

## Cameras ##
### Creating an instance of a primary camera ###
A primary camera generates a digital signal which dictates when secondary cameras acquire images. This allows for synchronous acquisition between multiple cameras.

```Python
>>> from llpyspin.capture import PrimaryCamera
>>> device = str(12345678) # primary camera serial number
>>> cam1 = PrimaryCamera(device)
>>> cam1.isPrimed() # check that the camera is primed
True
>>> cam1.prime() # you only need to prime the camera once
INFO : Video acquisition is already started
>>> cam1.trigger() # trigger camera
>>> cam1.stop() # stop acquisition
>>> cam1.release() # release camera
>>> cam1.isPrimed()
False
>>> cam1.prime() # you can re-prime the camera for subsequent recordings
>>> cam1.isPrimed()
True
```

### Modifying camera properties ###
Unlike the `llpyspin.capture.VideoStream` class which uses a class method to change acquisition properties, the `llpyspin.capture.PrimaryCamera` class uses class properties to modify properties of the video acquisition. Valid properties are framerate, exposure, binsize, and mode (mode refers to the stream buffer handling mode).

```Python
>>> cam1.framerate
120
>>> cam1.framerate = 60 # this calls the private class method _set
WARNING : Failed to set framerate to 60 because acquisition is ongoing. # properties can't be set after the camera is primed
>>> cam1.stop()
>>> cam1.framerate = 60
>>> cam1.framerate
60
>>> for attr in ['framerate','exposure','binsize','mode','foo']:
        print(hasattr(cam,attr))
True
True
True
True
False
```

### Adding one or more secondary cameras ###
A secondary camera's acquisition is coupled to the primary camera's acquisition.

```python
>>> from llpyspin.capture import SecondaryCamera
>>> device2 = str(87654321)
>>> cam2 = SecondaryCamera(device2)
>>> cam.isPrimed()
True
>>> cam.trigger() # the SecondaryCamera class lacks the trigger method
AttributeError: 'SecondaryCamera' object has no attribute 'trigger'
>>> cam3 ... # and so on
```

## Systems ##
TODO : Document this.

# Acknowledgements #
Big thanks to Dr. Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.
