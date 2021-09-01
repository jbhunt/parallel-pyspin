# parallel-pyspin #
This package provides another layer of abstraction on top of the Python wrapper for FLIR's [Spinnaker Software Development Kit](https://www.flir.com/products/spinnaker-sdk/) (SDK). This new layer of abstraction provides these additional features:

1. Parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package
2. Abstraction of the procedure for configuring multiple cameras for synchronous video acquisition

For documentation of the installation procedure and basic usage please refer to the repository's [wiki](https://github.com/jbhunt/parallel-pyspin/wiki). For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

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
To prepare the camera object for video recording, you need to call the `prime` method which required the file path including the filename for the video container and an optional keyword argument: `backend` which specifies the video writing backend. Supported video writing backends are `Spinnaker`, `OpenCV`, and `FFmpeg`. If using the `OpenCV` or `FFmpeg` backends, you will need to install some additional dependencies.
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
```Python
from llpysin import primary, secondary
cam1 = primary.PrimaryCamera(str(<serial number>))
cam1.prime('<file path>.mp4')
cam2 = secondary.SecondaryCamera(str(<serial number>))
cam2.prime('<file path>.mp4', cam1.framerate) # The prime method requires the framerate of the primary camera as an argument
cam1.trigger() # Triggering the primary camera will trigger the secondary camera
timestamps1 = cam1.stop() # Always stop the primary camera before the secondary camera
timestamps2 = cam2.stop()
cam1.release()
cam2.release()
```

### Recording videos in color ###
The default video format is grayscale encoded as an 8-bit unsigned integer; however, if you are using color image-capable cameras, you can produce color videos by setting the `color` keyword argument to `True` when you instantiate the camera objects.
```Python
cam1 = primary.PrimaryCamera(str(<serial number>), color=True) # very colorful, much wow
```

# Task list #
- [X] Make the camera objects accept serial numbers as integers
- [X] Send error messages back through the child proccess' queue
- [ ] Implement a periodic memory check which stops processes when the amount of available virtual memory exceeds a threshold
- [ ] Check that the access mode for each modifiable property of the camera pointer object is readable and writeable
- [ ] Write a unit test that tests each of the video writing backends
