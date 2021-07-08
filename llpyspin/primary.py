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
from .processes import MainProcess, ChildProcess, CameraError, queued
from .recording import VideoWriterFFmpeg, VideoWriterSpinnaker, VideoWritingError
from .secondary import SecondaryCamera

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
    def __init__(self, device: int=0, nickname: str=None):
        """
        """
        super().__init__(device, nickname)
        self._spawn_child_process(PrimaryCameraChildProcess)
        self._primed = False
        return

    def prime(
        self,
        filename: str,
        bitrate: int=1000000,
        backend: str='ffmpeg',
        timeout: int=1
        ):
        """
        """

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
        result, output = f(self, 'Failed to set buffer mode')

        # configure the camera to emit a digital signal
        @queued
        def f(child, camera, **kwargs):

            try:
                camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
                camera.LineSource.SetValue(PySpin.LineSource_ExposureActive)
                camera.LineSelector.SetValue(PySpin.LineSelector_Line2)
                camera.V3_3Enable.SetValue(True)

                return True, None

            except PySpin.SpinnakerException:
                return False, None

        # call the function
        result, output = f(self, 'Trigger configuration failed')

        # prime the camera for acquisition
        # NOTE - This is a special case in which the queued decorator won't
        #        work because trying to retrieve the result from the child's
        #        output queue will cause the main process to hang.
        def f(child, camera, **kwargs):

            try:

                # initialize the video writer
                if kwargs['backend'] == 'ffmpeg':
                    try:
                        writer = VideoWriterFFmpeg()
                    except VideoWritingError:
                        return False, []
                elif kwargs['backend'] == 'spinnaker':
                    try:
                        writer = VideoWriterSpinnaker()
                    except:
                        return False, []
                else:
                    return False, []
                writer.open(kwargs['filename'], kwargs['shape'], kwargs['framerate'], kwargs['bitrate'])

                # create the timestamps file
                if kwargs['timestamp']:
                    # TODO - implement a timestamping procedure
                    pass

                timestamps = list()

                # wait for the trigger event
                child.trigger.wait()

                # begin acquisition
                camera.BeginAcquisition()

                # main acquisition loop
                while child.acquiring.value:

                    try:
                        pointer = camera.GetNextImage(kwargs['timeout'])
                        if pointer.IsIncomplete():
                            continue
                        else:
                            if len(timestamps) == 0:
                                t0 = pointer.GetTimeStamp()
                                timestamps.append(0)
                            else:
                                tn = (pointer.GetTimeStamp() - t0) / 1000000
                                timestamps.append(tn)
                            writer.write(pointer)

                    except PySpin.SpinnakerException:
                        continue

                    pointer.Release()

                # suspend image acquisition to empty out the device buffer
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                # empty out the computer's device buffer
                while True:
                    try:
                        pointer = camera.GetNextImage(kwargs['timeout'])
                        if pointer.IsIncomplete():
                            continue
                        else:
                            if len(timestamps) == 0:
                                t0 = pointer.GetTimeStamp()
                                timestamps.append(0)
                            else:
                                tn = (pointer.GetTimeStamp() - t0) / 1000000
                                timestamps.append(tn)
                            writer.write(pointer)

                    except PySpin.SpinnakerException:
                        break

                # stop acquisition immediately
                camera.EndAcquisition()

                # turn the trigger mode back off
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                #
                writer.close()

                return True, timestamps

            except PySpin.SpinnakerException:
                return False, None

        # kwargs for configuring up the video writing
        kwargs = {
            'filename'  : filename,
            'timestamp' : timestamp,
            'shape'     : (self.height, self.width),
            'framerate' : self.framerate,
            'bitrate'   : bitrate,
            'backend'   : backend,
            'timeout'   : timeout
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

        # set the shared acquisition flag to True
        self._child.acquiring.value = 1

        # release the software trigger
        self._child.trigger.set()

        return

    def stop(self):
        """
        Stop video acquisition
        """

        if not self.primed:
            raise CameraError('Camera is not acquiring')

        # stop acquisition in the child process main loop
        self._child.acquiring.value = 0

        # release the trigger (in the case of abortion before the trigger method is called)
        if not self._child.trigger.is_set():
            self._child.trigger.set()

        # retrieve the result of video acquisition from the child's output queue
        result, timestamps = self._child.oq.get()

        # end acquisition and reset the camera
        @queued
        def f(obj, camera, **kwargs):
            try:
                camera.DeInit()
                return True, None
            except PySpin.SpinnakerException:
                return False, None

        result, output = f(self, 'Failed to stop video acquisition')

        # join the child process
        self._join_child_process()

        # reset the primed and locked flags
        self._primed = False
        self._locked = False

        # respawn the child process
        self._spawn_child_process(PrimaryCameraChildProcess)

        return timestamps

    #
    @property
    def primed(self):
        return self._primed
