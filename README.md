# parallel-pyspin #
For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Table of contents #
1. [Description](https://github.com/jbhunt/parallel-pyspin/#description)
   1. [Parallel camera operation](https://github.com/jbhunt/parallel-pyspin/#parallel-camera-operation)
   2. [Synchronous video acquisition](https://github.com/jbhunt/parallel-pyspin/#synchronous-video-acquisition)
2. [Installation](https://github.com/jbhunt/parallel-pyspin/#installation)
   1. [Installing parallel-pyspin](https://github.com/jbhunt/parallel-pyspin/#installing-parallel-pyspin)
   2. [Installing PySpin](https://github.com/jbhunt/parallel-pyspin/#installing-spinnaker-and-pyspin)
      1. [Method 1](https://github.com/jbhunt/parallel-pyspin/#method-1)
      2. [Method 2](https://github.com/jbhunt/parallel-pyspin/#method-2)
3. [Usage](https://github.com/jbhunt/parallel-pyspin/#usage)
   1. [Streaming](https://github.com/jbhunt/parallel-pyspin/#streaming)
      1. [Creating a video stream](https://github.com/jbhunt/parallel-pyspin/#creating-a-video-stream)
      2. [Modifying video stream properties](https://github.com/jbhunt/parallel-pyspin/#modifying-video-stream-properties)
   2. [Cameras](https://github.com/jbhunt/parallel-pyspin/#cameras)
      1. [Creating an instance of a primary camera](https://github.com/jbhunt/parallel-pyspin/#creating-an-instance-of-a-primary-camera)
      2. [Adding one or more secondary cameras](https://github.com/jbhunt/parallel-pyspin/#modifying-camera-properties)
4. [Task list](https://github.com/jbhunt/parallel-pyspin/#task-list)
5. [Contributers](https://github.com/jbhunt/parallel-pyspin/#contributers)

# 1. Description #
This package provides another layer of abstraction on top of [PySpin](https://www.flir.com/products/spinnaker-sdk/) (the Python wrapper for FLIR's Spinnaker software development kit). This new layer of abstraction provides these additional features:

1. Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package.
2. Encapsulation of the procedure for configuring multiple cameras for synchronous video acquisition.

There are several other packages that have similar capabilities and motives. Feel free to check them out and see if they are better suited for your needs:

1. [simple_pyspin](https://github.com/klecknerlab/simple_pyspin)
2. [multi_pyspin](https://github.com/justinblaber/multi_pyspin)

Finally, this package was developed using two [Blackfly S USB3](https://www.flir.com/products/blackfly-s-usb3/) cameras, but in theory it should work with any USB3 or GigE camera (i.e., any camera supported by the Spinnaker SDK).

## Parallel camera operation ##
Camera operation is parallelized with the multiprocessing package. Each camera runs on its own process which is dynamically spawned and joined with the main process as needed. The child processes make use of the PySpin package to interact with the camera, and they communicate with the main process via process-safe mechanisms like queues.

## Synchronous video acquisition ##
TODO : Describe how the cameras are configured for simultaneous video acquisition

# Installation #
## Installing parallel-pyspin ##
You can install version 0.2.dev2 of this package via pip. This version has been tested, but not exhaustively. If you use it and find a bug feel free to open an issue.
1. `pip install parallel-pyspin==0.2.dev2`

You can also install the most recent pre-release version (0.2.dev3) by cloning the repository and running the setup script. Be warned, this version is completely untested and only video streaming is supported as of now.
1. `git clone https://github.com/jbhunt/parallel-pyspin.git`
2. `cd ./parallel-pyspin`
3. `python -m setup.py install`

## Installing Spinnaker and PySpin ##
The only other software this package depends on is the Spinnaker SDK and its Python wrapper - PySpin.

### Method 1 ###
You can install these dependencies yourself. Take a look [here](https://www.flir.com/products/spinnaker-sdk). If you are using an operating system other than Ubuntu 18.04 or a Python version less than 3.6, this is the recommended procedure.

### Method 2 ###
Alternatively, if you are using Ubuntu 18.04 and Python 3.6+ I created a script that takes care of the installation for you. Follow these steps:

1. There's a folder which contains some libraries, a list of dependencies, the PySpin Wheel, and the installation script [here](https://github.com/jbhunt/parallel-pyspin/tree/master/spinnaker). To download this folder you can either clone the whole github repository: `git clone https://github.com/jbhunt/parallel-pyspin/` or you can use subversion to download just this folder and its contents: `svn checkout https://github.com/jbhunt/parallel-pyspin/trunk/spinnaker`. If you don't already have subversion installed you can install it like this: `sudo apt-get install subversion`.

2. Part of the installation procedure is increasing the memory limit for USB device buffers. By default Ubuntu caps USB device buffers at 16 MB ([source](https://www.flir.com/support-center/iis/machine-vision/application-note/understanding-usbfs-on-linux)). This can cause issues if you are using a camera with high resolution or at a high framerate or when using multiple cameras. To permanently modify the limit on USB device buffers use the `--increase-memory-limit` flag and specify the new buffer size with the `--memory-limit` argument. Make sure to run the script with root privileges: `sudo python -m ./spinnaker/install.py --increase-memory-limit --memory-limit 1200`.

This script takes care of steps 1-3 of the procedures for installation outlined in the Spinnaker [README](https://github.com/jbhunt/parallel-pyspin/blob/master/spinnaker/README) as well as the installation of the PySpin Wheel. There are additional steps that you might need to complete if you are using a GigE camera or if you'd like to use the SpinView GUI.

# Usage #
## Streaming ##
### Creating a video stream ###
This example demonstrates how to use the `llpyspin.streaming.VideoStream` class to create a video stream for a single camera. This class operates almost exactly like OpenCV's [VideoCapture](https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html) class in that is has many of the same methods and functionality. Multiple video streams cannot be synchronized with each other.

```python
>>> from llpyspin import streaming
>>> device = 0 # device index
>>> cap = streaming.VideoStream(device)
>>> cap.isOpened()
True
>>> result,image = cap.read()
>>> result
True
>>> image.shape
(1080,1440)
>>> cap.release()
```

### Modifying video stream properties ###
Unlike OpenCV's VideoCapture class which uses a 'get' and 'set' class method to query and assign property values, the VideoStream class uses Python properties to get and set properties of video acquisition. This interface applies to the camera classes as well.

``` python
>>> cap.framerate
30
>>> cap.framerate = 10
INFO : setting framerate to 10 fps
>>> cap.framerate
10
>>> cap.framerate = 120 # the properties are constrained
WARNING : failed to set framerate to 120 fps
>>> cam.binsize
1
>>> cam.exposure
1500
>>> cam.roi
(0, 0, 1440, 1080)
```

## Cameras ##
### Creating an instance of a primary camera ###

```Python
>>> from llpyspin import primary
>>> device = str(12345678) # primary camera serial number
>>> cam1 = primary.PrimaryCamera(device)
>>> cam1.primed # check that the camera is primed
True
>>> cam1.prime() # you only need to prime the camera once
INFO : video acquisition is already started
>>> cam1.framerate = 10 # the camera is locked when it is primed
<traceback>
Exception : the acquisition lock is engaged
>>> cam1.trigger() # trigger camera
>>> cam1.stop() # stop acquisition
>>> cam1.primed
False
>>> cam1.framerate = 10 # the camera is unlocked now
INFO : setting framerate to 10 fps
>>> cam1.prime() # you can re-prime the camera for subsequent recordings
>>> cam1.primed
True
>>> cam1.release() # be sure to clean up when you're done
```

### Adding one or more secondary cameras ###
A secondary camera's acquisition is coupled to the primary camera's acquisition via a hardware trigger.

```python
>>> from llpyspin import secondary
>>> device2 = str(87654321)
>>> cam2 = secondary.SecondaryCamera(device2)
>>> cam2.primed
True
>>> cam2.trigger() # the SecondaryCamera class has no trigger method
<traceback>
AttributeError: 'SecondaryCamera' object has no attribute 'trigger'
```

# Task list #
- [x] Get rid of the config.yaml file in favor of hardcoding all default properties in the constants module.
- [x] Move from using queues to implement the camera trigger to using a multiprocessing Event object.
- [x] Determine the resolution of the camera's sensor automatically
- [ ] Create a test script
- [ ] Implement the acquisition lock in the VideoStream class

# Contributors #
Big thanks to Dr. Ryan Williamson and the Scientific Computing Core at the University of Colorado, Anschutz Medical Campus.
