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
from .dummy import DummyCameraPointer
from .processes import MainProcess, ChildProcess, CameraError, queued, GETBY_DUMMY_CAMERA, GETBY_DEVICE_INDEX, GETBY_SERIAL_NUMBER
from .recording import FFmpegVideoWriter, SpinnakerVideoWriter, OpenCVVideoWriter, VideoWritingError
from .secondary import SecondaryCamera

class PrimaryCameraChildProcess(ChildProcess):
    """
    """

    def __init__(self, value=0, getby=GETBY_DEVICE_INDEX) -> None:
        """
        """

        # acquisition trigger
        self.trigger = mp.Event()

        # init
        super().__init__(value, getby)

        return

class PrimaryCamera(MainProcess):
    """
    """
    def __init__(
        self,
        serial_number : int=None,
        device_index  : int=None,
        nickname      : str=None,
        dummy         : bool=False,
        color         : bool=False
        ):
        """
        """

        super().__init__(serial_number, device_index, nickname, dummy, color)
        self._spawn_child_process(PrimaryCameraChildProcess)
        self._primed = False
        return

    def prime(
        self,
        filename: str,
        bitrate: int=1000000,
        backend: str='Spinnaker',
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

        # reset the trigger if priming after instantiation
        if self._child.trigger.is_set():
            self._child.trigger.clear()

        # Reset the frame counter
        if self._child.shared_frame_counter.value != 0:
            self._child.shared_frame_counter.value = 0

        # set the buffer handling mode to oldest first (instead of newest only)
        # and increase the number of bufered images allowed in memory
        @queued
        def f(child, pointer, **kwargs):
            try:
                pointer.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                pointer.TLStream.StreamBufferCountMode.SetValue(PySpin.StreamBufferCountMode_Manual)
                pointer.TLStream.StreamBufferCountManual.SetValue(pointer.TLStream.StreamBufferCountManual.GetMax())
                return True, None, None
            except PySpin.SpinnakerException:
                return False, None, f'Failed to set the stream buffer handling mode property'

        # call the function
        result, output, message = f(main=self)

        # configure the camera to emit a digital signal
        @queued
        def f(child, pointer, **kwargs):

            try:
                pointer.LineSelector.SetValue(PySpin.LineSelector_Line1)
                pointer.LineSource.SetValue(PySpin.LineSource_ExposureActive)
                pointer.LineSelector.SetValue(PySpin.LineSelector_Line2)
                pointer.V3_3Enable.SetValue(True)

                return True, None, None

            except PySpin.SpinnakerException:
                return False, None, f'Failed to configure the trigger'

        # call the function
        result, output, message = f(main=self)

        # prime the camera for acquisition
        # NOTE - This is a special case in which the queued decorator won't
        #        work because trying to retrieve the result from the child's
        #        output queue will cause the main process to hang.
        def f(child, pointer, **kwargs):

            #
            if isinstance(pointer, DummyCameraPointer):
                dummy = True
            else:
                dummy = False

            # initialize the video writer (and send the result back to the main process)
            try:
                backend = kwargs['backend']
                if backend in ['ffmpeg', 'FFmpeg']:
                    writer = FFmpegVideoWriter(color=kwargs['color'])
                elif backend in ['spinnaker', 'Spinnaker', 'PySpin']:
                    writer = SpinnakerVideoWriter(color=kwargs['color'])
                elif backend in ['opencv', 'OpenCV', 'cv2']:
                    writer = OpenCVVideoWriter(color=kwargs['color'])
                else:
                    item = (
                        False, f'{backend} is not a valid video writing backend'
                    )
                    child.oq.put(item)
                    return (None, None, None)

                writer.open(kwargs['filename'], kwargs['shape'], kwargs['framerate'], kwargs['bitrate'])
                item = (True, None)
                child.oq.put(item)

            except:
                item = (
                    False, f'Failed to open video writer (backend={backend})'
                )
                child.oq.put(item)
                return (None, None, None)

            # acquisition
            try:

                # list of timestamps
                timestamps = list()

                # wait for the trigger event
                child.trigger.wait()

                # begin acquisition
                pointer.BeginAcquisition()

                # main acquisition loop
                while child.acquiring.value:

                    try:

                        # Grab the next frame from the buffer
                        frame = pointer.GetNextImage(kwargs['timeout'])

                        # Increment the shared frame counter
                        child.shared_frame_counter.value += 1

                        # Write the frame to the video container
                        if frame.IsIncomplete():
                            continue
                        elif dummy:
                            writer.write(frame)
                        else:
                            if len(timestamps) == 0:
                                t0 = frame.GetTimeStamp()
                                timestamps.append(0.0)
                            else:
                                tn = (frame.GetTimeStamp() - t0) / 1000000
                                timestamps.append(tn)
                            writer.write(frame)
                            frame.Release()

                    except PySpin.SpinnakerException:
                        continue

                # Suspend image acquisition to empty out the device buffer
                pointer.TriggerMode.SetValue(PySpin.TriggerMode_On)

                # Empty out the host computer's device buffer
                while True:
                    try:

                        # Grab the next frame from the buffer
                        frame = pointer.GetNextImage(kwargs['timeout'])

                        # Increment the shared frame counter
                        child.shared_frame_counter.value += 1

                        if frame.IsIncomplete():
                            continue
                        elif dummy:
                            writer.write(frame)
                        else:
                            if len(timestamps) == 0:
                                t0 = frame.GetTimeStamp()
                                timestamps.append(0.0)
                            else:
                                tn = (frame.GetTimeStamp() - t0) / 1000000
                                timestamps.append(tn)
                            writer.write(frame)
                            frame.Release()

                    except PySpin.SpinnakerException:
                        break

                # stop acquisition immediately
                pointer.EndAcquisition()

                # turn the trigger mode back off
                pointer.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                #
                try:
                    writer.close()
                except:
                    return False, timestamps, f'Failed to close video writer (backend={backend})'

                return True, timestamps, None

            except PySpin.SpinnakerException as e:
                print(e)
                return False, None, f'Video acquisition failed'

        # kwargs for configuring up the video writing
        kwargs = {
            'filename'  : filename,
            'shape'     : (self.height, self.width),
            'framerate' : self.framerate,
            'bitrate'   : bitrate,
            'backend'   : backend,
            'timeout'   : timeout,
            'color'     : self.color
        }

        # place the function in the input queue
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)

        # check that the video writing setup was successful
        result, message = self._child.oq.get()
        if result == False:
            self._child.oq.get() # empty out the output queue
            raise CameraError(message)

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
            # TODO: Delete the video recording for an aborted acquisition run
            self._child.trigger.set()

        # retrieve the result of video acquisition from the child's output queue
        result, timestamps, message = self._child.oq.get()
        if result == False:
            raise CameraError(message)

        # reset the primed and locked flags
        self._primed = False
        self._locked = False

        return np.array(timestamps)

    def release(self):
        """
        """

        self._join_child_process()

        return

    #
    @property
    def primed(self):
        return self._primed
