# parallel-pyspin #
This package provides another layer of abstraction on top of the Python wrapper for FLIR's [Spinnaker Software Development Kit](https://www.flir.com/products/spinnaker-sdk/) (SDK). This new layer of abstraction provides these additional features:

1. Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package
2. Abstraction of the procedure for configuring multiple cameras for synchronous video acquisition

For documentation of the installation procedure and basic usage please refer to the repository's [wiki](https://github.com/jbhunt/parallel-pyspin/wiki). For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Installation #
### Installing parallel-pyspin ###
To install this package, clone the github repository and run the `setup.py` script.
```
cd <wherever you want the repo to live>
git clone https://github.com/jbhunt/parallel-pyspin.git
cd ./parallel-pyspin
python setup.py install
```

### Installing the Spinnaker SDK and PySpin ###
This package depends on the Spinnaker SDK and its Python wrapper - PySpin. You will need to manually install this dependency (sorry, there's no way to automate it).

#### Method 1 ####
You can follow the procedure for installation provided by FLIR. Take a look [here](https://www.flir.com/products/spinnaker-sdk). If you are using an operating system other than Ubuntu 18.04 this is the recommended approach.

#### Method 2 ####
Alternatively, if you are using Ubuntu 18.04, I created a script that takes care of the installation for you. Follow these steps:

1. There's a folder which contains some libraries, a list of dependencies, the PySpin Wheel, and an installation script [here](https://github.com/jbhunt/parallel-pyspin/tree/master/spinnaker). To download this folder you can either clone the whole github repository (including this folder): `git clone https://github.com/jbhunt/parallel-pyspin/`, or you can use subversion to download just this folder and its contents: `svn checkout https://github.com/jbhunt/parallel-pyspin/trunk/spinnaker`. If you don't already have subversion installed you can install it like this: `sudo apt-get install subversion`.

2. Part of the installation procedure is increasing the memory limit for USB device buffers. By default Ubuntu caps USB device buffers at 16 MB ([source](https://www.flir.com/support-center/iis/machine-vision/application-note/understanding-usbfs-on-linux)). The USB device buffer size limit is increased to prevent dropped frames when recording with multiple cameras at high framerates and large image sizes. To permanently modify the limit on USB device buffers use the `--increase-memory-limit` flag and specify the new buffer size with the `--memory-limit` argument: `sudo python -m ./spinnaker/install.py --increase-memory-limit --memory-limit 1200`.

This script takes care of steps 1-3 of the procedures for installation outlined in the Spinnaker [README](https://github.com/jbhunt/parallel-pyspin/blob/master/spinnaker/README) as well as the installation of the PySpin Wheel. There are additional steps that you might need to complete if you are using a GigE camera or if you'd like to use the SpinView GUI.

### Installing FFmpeg (optional) ###
You need to install FFmpeg if you'd like to use it as the backend for video writing. Using FFmpeg to write the videos can help prevent dropping frames at high framerates because the FFmpeg video writing backend is parallelized; whereas, the Spinnaker SDK video writing backend is not. If you are using Ubuntu (Linux), you can simply install it with apt:

1. `sudo apt install ffmpeg`

If you are using Windows, you'll need to install it yourself and verify that the installation was successful. This is the basic installation procedure:

1. Download the zip file from their website [here](https://www.ffmpeg.org/download.html).
2. Extract the zip file and move it to wherever you would like it to live and rename it `ffmpeg`. I recommend moving it to the root of the C:\ drive.
3. Append `<path to install>\ffmpeg\bin` to the `PATH` environmental variable.

[Here](https://www.wikihow.com/Install-FFmpeg-on-Windows) is also a simple tutorial on how to do this step-by-step.

### Installing opencv-python (optional) ###
You need to install the Python wrapper for OpenCV if you want to use OpenCV for the video writing backend. Similar to the FFmpeg video writing backend, the OpenCV backend is parallelized to offload the video writing operation to a separate process. To install this package:

1. pip install opencv-python

# Basic usage #
### Creating an instance of a primary camera ###
Cameras are represented as objects. Each camera object requires either a serial number or device index to be instantiated.
```Python
from llpyspin import primary
cam1 = primary.PrimaryCamera(serial_number=12345678)
```
or
```Python
cam1 = primary.PrimaryCamera(device_index=0)
```
To prepare the camera object for video recording, you need to call the `prime` method which requires the file path including the filename for the video container and an optional keyword argument: `backend` which specifies the video writing backend. Supported video writing backends are `Spinnaker`, `OpenCV`, and `FFmpeg`. If using the `OpenCV` or `FFmpeg` backends, you will need to install some additional dependencies.
```Python
cam1.prime('<file path>.mp4', backend='Spinnaker')
```
Once the camera object is primed, call the `trigger` method to start recording.
```Python
cam1.trigger()
```
When you are done recording, call the `stop` method. This will return the timestamps (in milliseconds) for each frame in the video recording.
```Python
timestamps = cam1.stop() # the stop method returns the timestamps for each frame (in milliseconds)
```
You can call the `prime` method as many times as you want, but when you are done recording, call the `release` method to clean up.
```Python
cam1.release() # make sure to release the camera when you are done
```

### Adding one or more secondary cameras ###
The `SecondaryCamera` object is used to handle cameras which are triggered by a physical signal. This object operates almost exactly like the `PrimaryCamera` object with the exception that there is no `trigger` method. Calling the `prime` method will prompt the camera object to enter an acquisition loop which waits for images to enter the camera's image buffer.
```Python
from llpysin import primary, secondary
cam1 = primary.PrimaryCamera(serial_number=12345678)
cam1.prime('<file path>.mp4')
cam2 = secondary.SecondaryCamera(str(serial_number=87654321)
```
Note that the `prime` method requires the framerate of the primary camera in frames per second as the second positional argument. This ensures the primary camera's framerate does not exceed what the secondary camera can achieve.
```Python
cam2.prime('<file path>.mp4', cam1.framerate) # The prime method requires the framerate of the primary camera as an argument
cam1.trigger() # Triggering the primary camera will trigger the secondary camera
```
When stopping acquisition, always stop the primary camera before the secondary camera(s). This ensures that the primary camera does not record more images than the secondary camera(s).
```Python
timestamps1 = cam1.stop() # Always stop the primary camera before the secondary camera
timestamps2 = cam2.stop()
```
And make sure to clean up when you're done (the order doesn't matter).
```Python
cam1.release()
cam2.release()
```

### Recording videos in color ###
The default pixel format for videos recordings is monochrome encoded as an 8-bit unsigned integer; however, if you are using color image-capable cameras, you can produce color videos by setting the `color` keyword argument to `True` when you instantiate the camera objects.
```Python
cam1 = primary.PrimaryCamera(serial_number=12345678, color=True) # very colorful, much wow
```
You can also modify this property outside of video recordings by setting the value of the `color` property.
```Python
cam1.color = False # 8-bit grayscale
cam1.color = True # 8-bit RGB
```

### Modifying acquisition properties ###
There are 4 acquisition properties you can modify:
1. `framerate`: Camera framerate in frames per second
2. `exposure`: Camera exposure time in microseconds
3. `binsize`: A tuple (or integer) which specifies horizontal and vertical binning in pixels
4. `roi`: A tuple which defines a rectangular region of interest (x offset, y offset, width, height) in pixels

When you instantiate a camera object, these properties are assigned default values. You can change the value of a given property by invoking the setter method.
```Python
cam1.framerate # Returns the default framerate (30 fps)
cam1.framerate = 60 # Invoke the setter method
cam1.framerate # Returns 60 now (if the call was successful)
```
These properties are somewhat intelligent in that they will raise an error if the target value of the property exceeds the capability of the camera.
```Python
cam1.framerate = 1000000 # This will raise an error
```
Lastly, acquisition properties cannot be set during video acquisition. If you try to do this (after calling the `prime` and `trigger` methods), you will get an error.
```Python
cam1.prime('<file path>')
cam1.trigger()
cam1.framerate = 60 # Raises an error without interrupting acquisition
```

### Streaming video ###
In case you prefer to stream video instead of creating video recordings (useful for real-time applications), use the `VideoStream` object. This object operates a lot like OpenCV's `VideoCapture` object if you are familiar with it. Instead of buffering as many images as possible and writing them to a video container, the `VideoStream` object holds only a single image in memory at any given time. This image is updated as fast as possible (or more accurately at the camera's framerate).
```Python
from llpyspin import streaming
cap = streaming.VideoStream(serial_number=12345678)
```
Calling the `read` method will return the result of the call and the image as a Numpy array.
```Python
result, image = cap.read()
```
Make sure to close the stream when you are done.
```Python
stream.close()
```

### Dummy camera ###
Testing without access to a physical device can be accomplished by using the `dummy` keyword argument.
```Python
dummy = primary.PrimaryCamera(dummy=True)
```
This dummy camera object operates exactly like an actual camera object including being able to record videos (of a sequence of noisy images).

# Task list #
- [X] Make the camera objects accept serial numbers as integers
- [X] Send error messages back through the child proccess' queue
- [ ] Implement a periodic memory check which stops processes when the amount of available virtual memory exceeds a threshold
- [ ] Check that the access mode for each modifiable property of the camera pointer object is readable and writeable
- [ ] Write a unit test that tests each of the video writing backends
