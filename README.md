# parallel-pyspin #
For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Table of contents #
1. [Description](https://github.com/jbhunt/parallel-pyspin/#1-description)
   1. [Parallel camera operation](https://github.com/jbhunt/parallel-pyspin/#11-parallel-camera-operation)
   2. [Synchronous video acquisition](https://github.com/jbhunt/parallel-pyspin/#12-synchronous-video-acquisition)
2. [Installation](https://github.com/jbhunt/parallel-pyspin/#2-installation)
   1. [Installing parallel-pyspin](https://github.com/jbhunt/parallel-pyspin/#21-installing-parallel-pyspin)
   2. [Installing PySpin](https://github.com/jbhunt/parallel-pyspin/#22-installing-pyspin)
      1. [Method 1](https://github.com/jbhunt/parallel-pyspin/#221-method-1)
      2. [Method 2](https://github.com/jbhunt/parallel-pyspin/#222-method-2)
3. [Usage](https://github.com/jbhunt/parallel-pyspin/#3-usage)
   1. [Streaming](https://github.com/jbhunt/parallel-pyspin/#31-streaming)
      1. [Creating a video stream](https://github.com/jbhunt/parallel-pyspin/#311-creating-a-video-stream)
      2. [Modifying video stream properties](https://github.com/jbhunt/parallel-pyspin/#312-modifying-video-stream-properties)
   2. [Cameras](https://github.com/jbhunt/parallel-pyspin/#32-cameras)
      1. [Creating an instance of a primary camera](https://github.com/jbhunt/parallel-pyspin/#321-creating-an-instance-of-a-primary-camera)
      2. [Adding one or more secondary cameras](https://github.com/jbhunt/parallel-pyspin/#322-modifying-camera-properties)
4. [Contributers](https://github.com/jbhunt/parallel-pyspin/#4-contributers)
5. [TODO list](https://github.com/jbhunt/parallel-pyspin/#5-todo-list)

# 1. Description #
This package provides another layer of abstraction on top of [PySpin](https://www.flir.com/products/spinnaker-sdk/) (the Python wrapper for FLIR's Spinnaker software development kit). This new layer of abstraction provides these additional features:

1. Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) module.
2. Semi-automatic configuration for synchronous video acquisition with multiple cameras

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
You can install most recent pre-release version (0.2.dev2) of this package via pip:
1. `pip install parallel-pyspin==0.2.dev2`

You can also clone this repository and run the setup script:
1. `git clone https://github.com/jbhunt/parallel-pyspin.git`
2. `python -m setup.py install`

Be warned, the github repo is one development version ahead of the PYPI package. It's untested and not entirely bug-free. Use it at your own risk.

## 2.2. Installing PySpin ##
The only other software this package depends on is the Spinnaker SDK and the PySpin package.

### Method 1 ###
You can install these dependencies yourself. Take a look [here](https://www.flir.com/products/spinnaker-sdk). If you are using an operating system other than Ubuntu 18.04 or a Python version less than 3.6, this is the recommended procedure.

### Method 2 ###
Alternatively, if you are using Ubuntu 18.04 and Python 3.6+ you can run [this script](https://github.com/jbhunt/parallel-pyspin/tree/master/spinnaker/install.py) and it should take care of the installation for you.

1. There's a folder which contains some libraries, a list of dependencies and the PySpin Wheel [here](https://github.com/jbhunt/parallel-pyspin/tree/master/spinnaker). To download this file you can either clone the whole github repository: `git clone https://github.com/jbhunt/parallel-pyspin/` or you can use subversion to download just this folder and its contents: `svn checkout https://github.com/jbhunt/parallel-pyspin/trunk/spinnaker`. To install subversion if you don't already have it installed: `sudo apt-get install subversion`.

2. Part of the installation procedure is increasing the memory limit for USB device buffers. By default Ubuntu caps USB device buffers at 16 MB ([source](https://www.flir.com/support-center/iis/machine-vision/application-note/understanding-usbfs-on-linux)). This can cause issues if you are using a camera with high resolution or at a high framerate or when using multiple cameras. To permanently modify the limit on USB device buffers use the `--increase-memory-limit` flag and specify the new buffer size with the `--memory-limit` argument. Make sure to run the script with root privileges: `sudo python -m ./install.py --increase-memory-limit --memory-limit 1200`.

This script takes care of steps 1-3 of the procedures for installation outlined in the Spinnaker [README](https://github.com/jbhunt/parallel-pyspin/blob/master/spinnaker/README) as well as the installation of the PySpin Wheel. There are additional steps that you might need to complete if you are using a GigE camera or if you'd like to use the SpinView GUI.

# 3. Usage #
## 3.1. Streaming ##
### 3.1.1. Creating a video stream ###
This example demonstrates how to use the `llpyspin.capture.VideoStream` class to create a video stream for a single camera. This class operates almost exactly like OpenCV's [VideoCapture](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html) class in that is has many of the same methods and functionality. Multiple video streams cannot be synchronized with each other.

```python
>>> import llpyspin
>>> device = 0 # device index
>>> cap = llpyspin.VideoStream(device)
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
Unlike OpenCV's VideoCapture class which uses a 'get' and 'set' class method to query and assign property values, respectively, the VideoStream class uses Python properties to get and set properties of video acquisition. This interface applies to the camera classes as well.

``` python
>>> cap.framerate
60
>>> cap.framerate = 100
>>> cap.framerate = 121 # some of the properties are constrained
WARNING : The requested framerate of 121 fps falls outside the range of permitted values (1 - 120). Defaulting to 60 fps.
>>> for attr in ['_framerate','_exposure','_binsize']:
        print(property.strip('_') + f' : {self.__getattribute__(attr)}')
framerate : 60
exposure : 1500
binsize : 2
```

## 3.2. Cameras ##
### 3.2.1. Creating an instance of a primary camera ###
A primary camera generates a digital signal which dictates when secondary cameras acquire images. This allows for synchronous acquisition between multiple cameras.

```Python
>>> device = str(12345678) # primary camera serial number
>>> cam1 = llpyspin.PrimaryCamera(device)
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

### 3.2.2. Adding one or more secondary cameras ###
A secondary camera's acquisition is coupled to the primary camera's acquisition.

```python
>>> device2 = str(87654321)
>>> cam2 = llpyspin.SecondaryCamera(device2)
>>> cam2.primed
True
>>> cam2.trigger() # the SecondaryCamera class has no trigger method
AttributeError: 'SecondaryCamera' object has no attribute 'trigger'
```

# 4. Contributors #
Big thanks to Dr. Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.

# 5. TODO list #
- [ ] Move from using queues to implement the camera trigger to using a multiprocessing Event object.
- [x] Get rid of the config.yaml file in favor of hardcoding all default properties in the constants module.
