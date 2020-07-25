# parallel-pyspin #
For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Table of contents #
1. [Description](https://github.com/jbhunt/parallel-pyspin/#1-description)
   1. [Parallel camera operation](https://github.com/jbhunt/parallel-pyspin/#11-parallel-camera-operation)
   2. [Synchronous video acquisition](https://github.com/jbhunt/parallel-pyspin/#12-synchronous-video-acquisition)
2. [Installation](https://github.com/jbhunt/parallel-pyspin/#2-installation)
   1. [Installing parallel-pyspin](https://github.com/jbhunt/parallel-pyspin/#21-installing-parallel-pyspin)
   2. [Installing PySpin](https://github.com/jbhunt/parallel-pyspin/#22-installing-pyspin)
3. [Usage](https://github.com/jbhunt/parallel-pyspin/#3-usage)
   1. [Streaming](https://github.com/jbhunt/parallel-pyspin/#31-streaming)
      1. [Creating a video stream](https://github.com/jbhunt/parallel-pyspin/#311-creating-a-video-stream)
      2. [Modifying video stream properties](https://github.com/jbhunt/parallel-pyspin/#312-modifying-video-stream-properties)
   2. [Cameras](https://github.com/jbhunt/parallel-pyspin/#32-cameras)
      1. [Creating an instance of a primary camera](https://github.com/jbhunt/parallel-pyspin/#321-creating-an-instance-of-a-primary-camera)
      2. [Modify camera properties](https://github.com/jbhunt/parallel-pyspin/#322-modifying-camera-properties)
      3. [Adding one or more secondary cameras](https://github.com/jbhunt/parallel-pyspin/#323-modifying-camera-properties)
   3. [System](https://github.com/jbhunt/parallel-pyspin/#33-systems)
4. [Contributers](https://github.com/jbhunt/parallel-pyspin/#4-contributers)

# 1. Description #
This package provides another layer of abstraction on top of [PySpin](https://www.flir.com/products/spinnaker-sdk/) (the Python wrapper for FLIR's Spinnaker software development kit). This new layer of abstraction provides these additional features:

1. Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package
2. True synchronous video acquisition for multiple cameras

There are several other packages that have similar capabilities and motives, but it doesn't seem like these projects are actively maintained. Feel free to check them out and see if they are better suited for your needs:

1. [multi_pyspin](https://github.com/justinblaber/multi_pyspin)
2. [simple_pyspin](https://github.com/klecknerlab/simple_pyspin)

Finally, this package was developed using two [Blackfly S USB3](https://www.flir.com/products/blackfly-s-usb3/) cameras, but in theory it should work with any USB3 or GigE camera (i.e., any camera supported by the Spinnaker SDK).

## 1.1 Parallel camera operation ##
TODO : Describe how multiprocessing is used to parallelize the camera operation

## 1.2. Synchronous video acquisition ##
TODO : Describe how the cameras are configured for simultaneous video acquisition

# 2. Installation #
## 2.1. Installing parallel-pyspin ##
You can install most recent pre-release version (0.1dev4) of this package via pip:
1. `pip install parallel-pyspin==0.1dev4`

You can also clone this repository and run the setup script:
1. `git clone https://github.com/jbhunt/parallel-pyspin.git`
2. `python -m setup.py install`

## 2.2. Installing PySpin ##
TODO : Document this.

# 3. Usage #
## 3.1. Streaming ##
### 3.1.1. Creating a video stream ###
This example demonstrates how to use the `llpyspin.capture.VideoStream` class to create a video stream for a single camera. This class operates almost exactly like OpenCV's [VideoCapture](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html) class in that is has many of the same methods and functionality. Multiple video streams cannot be synchronized with each other.

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

### 3.1.2. Modifying video stream properties ###
You can modify a camera's framerate, exposure, or binsize using the stream's 'set' method. In this example the exposure is changed from the default value (1500 us) to a new target value. Supported capture properties are stored in the `llpyspin.constants` module. You can query the value of a capture property with the 'get' method.

``` python
>>> from llpyspin import constants as c
>>> cap.get(c.CAP_PROP_EXPOSURE)
1500
>>> cap.set(c.CAP_PROP_EXPOSURE,3000) # this restarts the child process
>>> cap.get(c.CAP_PROP_EXPOSURE)
3000
```

## 3.2. Cameras ##
### 3.2.1. Creating an instance of a primary camera ###
A primary camera generates a digital signal which dictates when secondary cameras acquire images. This allows for synchronous acquisition between multiple cameras.

```Python
>>> from llpyspin.capture import PrimaryCamera
>>> device = str(12345678) # primary camera serial number
>>> cam1 = PrimaryCamera(device)
>>> cam1.primed # check that the camera is primed
True
>>> cam1.prime() # you only need to prime the camera once
INFO : Video acquisition is already started
>>> cam1.trigger() # trigger camera
>>> cam1.stop() # stop acquisition
>>> cam1.release() # release camera
>>> cam1.primed
False
>>> cam1.prime() # you can re-prime the camera for subsequent recordings
>>> cam1.primed
True
```

### 3.2.2. Modifying camera properties ###
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

### 3.2.3. Adding one or more secondary cameras ###
A secondary camera's acquisition is coupled to the primary camera's acquisition.

```python
>>> from llpyspin.capture import SecondaryCamera
>>> device2 = str(87654321)
>>> cam2 = SecondaryCamera(device2)
>>> cam2.primed
True
>>> cam2.trigger() # the SecondaryCamera class lacks the trigger method
AttributeError: 'SecondaryCamera' object has no attribute 'trigger'
>>> cam3 ... # and so on
```

## 3.3. Systems ##
TODO : Document this.

# 4. Contributors #
Big thanks to Dr. Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.
