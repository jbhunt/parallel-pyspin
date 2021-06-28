# imports
import os
import dill
import PySpin
import logging
import numpy as np
import pathlib as pl
import multiprocessing as mp
from datetime import datetime as dt

# relative imports
from .processes  import MainProcess, ChildProcess, CameraError, queued
from .recording  import VideoWriterFFmpeg, VideoWriterSpinnaker

class PrimaryCameraChildProcess(ChildProcess):
    """
    """

    def __init__(self, device: int=0) -> None:
        """
        """

        # acquisition trigger
        self.trigger = mp.Event()

        super().__init__(device)

        return

class PrimaryCamera(MainProcess):
    """
    """
    def __init__(self, device: int=0):
        """
        """
        super().__init__(device)
        self._spawn_child_process(PrimaryCameraChildProcess)
        self._secondary_cameras = list()
        return

    def prime(self, filename: str, timestamp: bool=True, bitrate: int=1000000, backend: str='ffmpeg') -> None:
        """
        Get the camera ready to record

        keywords
        --------
        """

        # check the filename

        # stop acquisition if prime is called before the trigger method
        if self.primed:
            self.stop()

        # spawn a new child process
        if self._child is None:
            self._spawn_child_process(PrimaryCameraChildProcess)

        # set the buffer handling mode to oldest first (instead of newest only)
        @queued
        def f(child, camera, **kwargs):
            try:
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                return True, None
            except PySpin.SpinnakerException:
                return False, None

        # call the function
        result, output = f(self, 'Failed to set buffer handling mode')

        # configure the hardware trigger
        @queued
        def f(child, camera, **kwargs):

            try:
                # create a counter that tracks the onset sensor exposure
                camera.CounterSelector.SetValue(PySpin.CounterSelector_Counter0)
                camera.CounterEventSource.SetValue(PySpin.CounterEventSource_ExposureStart)
                camera.CounterTriggerSource.SetValue(PySpin.CounterTriggerSource_ExposureStart)
                camera.CounterTriggerActivation.SetValue(PySpin.CounterTriggerActivation_RisingEdge)

                # create a digital signal whose PWD is determined by the counter
                camera.LineSelector.SetValue(PySpin.LineSelector_Line2)
                camera.V3_3Enable.SetValue(True)
                camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
                camera.LineSource.SetValue(PySpin.LineSource_Counter0Active)

                #
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                camera.TriggerSource.SetValue(PySpin.TriggerSource_Software)
                camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                return True, None

            except PySpin.SpinnakerException:
                return False, None

        # call the function
        result, output = f(self, 'Trigger configuration failed')

        # begin acquisition
        # NOTE - This is a special case in which the queued decorator won't
        #        work because trying to retrieve the result from the child's
        #        output queue will cause the main process to hang.
        def f(child, camera, **kwargs):

            try:

                # begin acquisition
                camera.BeginAcquisition()

                # initialize the video writer
                if kwargs['backend'] == 'ffmpeg':
                    writer = VideoWriterFFmpeg()
                elif kwargs['backend'] == 'spinnaker':
                    writer = VideoWriterSpinnaker()
                else:
                    return False, None
                writer.open(kwargs['filename'], kwargs['shape'], kwargs['framerate'], kwargs['bitrate'])

                # create the timestamps file
                if kwargs['timestamp']:
                    # TODO - implement a timestamping procedure
                    pass

                # wait for the trigger event
                child.trigger.wait()

                # unset the trigger mode
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                # main acquisition loop
                while obj.acquiring.value:

                    try:
                        pointer = camera.GetNextImage(1)
                    except PySpin.SpinnakerException:
                        continue

                    if not pointer.IsIncomplete():
                        writer.write(pointer)

                    pointer.Release()


                # reset the trigger mode
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                #
                writer.close()
                return True, None

            except PySpin.SpinnakerException:
                return False, None

        # kwargs for configuring up the video writing
        kwargs = {
            'filename'  : filename,
            'timestamp' : timestamp,
            'shape'     : (self.height, self.width),
            'framerate' : self.framerate,
            'bitrate'   : bitrate,
            'backend'   : backend
        }

        # place the function in the input queue
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)

        #
        self._primed = True
        self._locked = True

        return

    def trigger(self):
        """
        Start video acquisition
        """

        if not self.primed:
            raise CameraError('Camera is not primed')

        # start all of the secondary cameras
        for camera in self.secondary_cameras:
            camera.start()

        # set the shared acquisition flag to True
        self._child.acquiring.value = 1

        # release the software trigger
        self._child.trigger.set()

        return

    def stop(self):
        """
        Stop video acquisition
        """

        if self._child.acquiring.value != 1:
            raise CameraError('Camera is not acquiring')

        # stop acquisition in the child process main loop
        self._child.acquiring.value = 0

        # release the trigger (in the case of abortion before the trigger method is called)
        if not self._child.trigger.is_set():
            self._child.trigger.set()

        # retrieve the result of video acquisition from the child's output queue
        result, output = self._child.oq.get()

        # end acquisition and reset the camera
        @queued
        def f(obj, camera, **kwargs):
            try:
                camera.EndAcquisition()
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
                camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
                camera.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
                camera.LineInverter.SetValue(True)
                camera.DeInit()
                return True, None
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, "Camera deactivation failed")

        # join the child process
        self._join_child_process()

        # reset the primed and locked flags
        self._primed = False
        self._locked = False

        # stop all of the secondary cameras
        for camera in self.secondary_cameras:
            camera.stop()

        return

    def prime_secondary_cameras(self, devices: list, filenames: list) -> None:
        """
        Prime the secondary camera(s) for video acquisition

        Keywords
        --------
        devices : list
            A list of the camera index or serial number for the secondary camera(s)
        filenames : list
            A list of the movie filenames for each secondary camera

        Notes
        -----
        Each filename must be an absolute file path with the .mp4 extension
        """

        #
        if self.locked:
            raise CameraError('Cannot prime secondary cameras during acquisition')

        # make sure the number of devices and the number of filenames is equal
        if len(devices) != len(filenames):
            raise ValueError('Unequal number of devices and filenames')

        # check that the destination folder for each movie file exists
        for filename in filenames:
            if not os.path.exists(os.path.dirname(filename)):
                raise CameraError(f'{filename} is not a valid filename')

        for device, filename in zip(devices, filenames):
            camera = SecondaryCamera(device)
            camera.prime(filename)
            self._secondary_cameras.append(camera)

        return

    @property
    def secondary_cameras(self):
        return self._secondary_cameras

    #
    @property
    def primed(self):
        return self._primed
