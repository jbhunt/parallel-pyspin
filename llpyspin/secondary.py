import dill
import PySpin
import numpy as np
import multiprocessing as mp

# relative imports
from .dummy import DummyCameraPointer
from .processes import MainProcess, ChildProcess, CameraError, queued
from .recording import FFmpegVideoWriter, SpinnakerVideoWriter, OpenCVVideoWriter, VideoWritingError

class SecondaryCamera(MainProcess):
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
        self._spawn_child_process(ChildProcess)
        self._primed = False

        return

    def prime(
        self,
        filename,
        primary_camera_framerate,
        bitrate=1000000,
        backend='Spinnaker',
        timeout=1
        ):
        """
        """

        if self.primed:
            raise CameraError('Camera is already primed')

        if self._child is None:
            self._spawn_child_process(ChildProcess)

        # NOTE - The secondary camera's framerate MUST be less than the primary
        #        camera's framerate (or the frequency of the external sync signal)
        #        or else frames will be dropped by the secondary camera

        # check if the secondary camera's framerate is < the primary camera's framerate
        if self.framerate < primary_camera_framerate:
            self.framerate = 'max'
        if self.framerate < primary_camera_framerate:
            raise CameraError("Secondary camera's framerate < primary camera's framerate")

        def f(child, pointer, **kwargs):

            # Set the dummy flag
            dummy = True if isinstance(pointer, DummyCameraPointer) else False

            # Initialize the video writer (and send the result back to the main process)
            try:
                backend = kwargs['backend']
                if backend in ['ffmpeg', 'FFmpeg']:
                    writer = FFmpegVideoWriter(color=kwargs['color'])
                elif backend in ['spinnaker', 'Spinnaker', 'PySpin', 'pyspin']:
                    writer = SpinnakerVideoWriter(color=kwargs['color'])
                elif backend in ['opencv', 'OpenCV', 'cv2', 'cv']:
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

            try:

                # set the streaming mode to oldest first
                pointer.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                pointer.TLStream.StreamBufferCountMode.SetValue(PySpin.StreamBufferCountMode_Manual)
                pointer.TLStream.StreamBufferCountManual.SetValue(pointer.TLStream.StreamBufferCountManual.GetMax())

                # configure the hardware trigger for a secondary camera
                pointer.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                pointer.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
                pointer.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                pointer.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge)
                pointer.TriggerMode.SetValue(PySpin.TriggerMode_On)

                #
                timestamps = list()

                # begin acquisition
                pointer.BeginAcquisition()

                # Counts the number of frames in the secondary camera's video recording
                local_frame_counter = 0

                # main loop
                while child.acquiring.value:

                    # Wait for the primary camera to begin acquisition of the next frame
                    if local_frame_counter >= child.shared_frame_counter.value:
                        continue

                    # There's a 1 ms timeout for the call to GetNextImage to prevent
                    # the secondary camera from blocking when video acquisition is
                    # aborted before the primary camera is triggered (see below).

                    try:
                        frame = pointer.GetNextImage(kwargs['timeout'])
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

                        # Increment the local frame counter
                        local_frame_counter += 1

                    except PySpin.SpinnakerException:
                        continue

                # Empty out the computer's device buffer
                while True:

                    # Exit the loop if the counters are equal
                    if local_frame_counter >= child.shared_frame_counter.value:
                        break

                    try:
                        frame = pointer.GetNextImage(kwargs['timeout'])
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

                        # Increment the local frame counter
                        local_frame_counter += 1

                    except PySpin.SpinnakerException:
                        break

                # stop acquisition
                pointer.EndAcquisition()

                # reset the trigger mode
                pointer.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                # close the video writer
                writer.close()

                return True, timestamps, None

            except PySpin.SpinnakerException:
                return False, None, f'Video acquisition failed'

        # NOTE - The acquisition flag needs to be set here before placing the
        #        acquisition function in the child's input queue
        self._child.acquiring.value = 1

        #
        kwargs = {
            'filename'  : filename,
            'shape'     : (self.height, self.width),
            'framerate' : primary_camera_framerate,
            'bitrate'   : bitrate,
            'backend'   : backend,
            'timeout'   : timeout,
            'color'     : self.color
        }
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)

        # check that the video writing setup was successful
        result, message = self._child.oq.get()
        if result == False:
            self._child.oq.get() # empty out the output queue
            raise CameraError(message)

        self._primed = True
        self._locked = True

        return

    def stop(self):
        """
        """

        if not self.primed:
            raise CameraError('Camera is not acquiring')

        # stop acquisition
        self._child.acquiring.value = 0

        # query the result of video acquisition
        result, timestamps, message = self._child.oq.get()

        self._primed = False
        self._locked = False

        return np.array(timestamps)

    def release(self):
        """
        """

        self._join_child_process()

        return

    @property
    def primed(self):
        return self._primed
