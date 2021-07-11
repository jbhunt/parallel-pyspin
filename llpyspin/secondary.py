import dill
import PySpin
import numpy as np
import multiprocessing as mp

# relative imports
from .processes import MainProcess, ChildProcess, CameraError, queued
from .recording import VideoWriterFFmpeg, VideoWriterSpinnaker, VideoWritingError

class SecondaryCamera(MainProcess):
    """
    """

    def __init__(self, device: int=1):
        """
        """

        super().__init__(device)
        self._spawn_child_process(ChildProcess)
        self._primed = False

        return

    def prime(self,
        filename,
        primary_camera_framerate,
        bitrate=1000000,
        backend='ffmpeg',
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
                elif kwargs['backend'] == 'OpenCV':
                    try:
                        writer = VideoWriterOpenCV()
                    except VideoWritingError:
                        return False, []
                else:
                    return False, []
                writer.open(kwargs['filename'], kwargs['shape'], kwargs['framerate'], kwargs['bitrate'])

                # set the streaming mode to oldest first
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)

                # configure the hardware trigger for a secondary camera
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
                camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                camera.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge)
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                #
                timestamps = list()

                # begin acquisition
                camera.BeginAcquisition()

                # main loop
                while child.acquiring.value:

                    # There's a 1 ms timeout for the call to GetNextImage to prevent
                    # the secondary camera from blocking when video acquisition is
                    # aborted before the primary camera is triggered (see below).

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

                        pointer.Release()

                    except PySpin.SpinnakerException:
                        continue

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

                # stop acquisition
                camera.EndAcquisition()

                # reset the trigger mode
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                # close the video writer
                writer.close()

                return True, timestamps

            except PySpin.SpinnakerException:
                return False, None

        # NOTE - The acquisition flag needs to be set here before placing the
        #        acquisition function in the child's input queue
        self._child.acquiring.value = 1

        #
        kwargs = {
            'filename'  : filename,
            'timestamp' : timestamp,
            'shape'     : (self.height, self.width),
            'framerate' : primary_camera_framerate,
            'bitrate'   : bitrate,
            'backend'   : backend,
            'timeout'   : timeout
        }
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)
        self._primed = True

        return

    def stop(self):
        """
        """

        if not self.primed:
            raise CameraError('Camera is not acquiring')

        # stop acquisition
        self._child.acquiring.value = 0

        # query the result of video acquisition
        result, timestamps = self._child.oq.get()

        @queued
        def f(obj, camera, **kwargs):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
                return True, None
            except:
                return False, None

        result, output = f(self, 'Failed to stop video acquisition')

        self._join_child_process()

        self._primed = False
        self._locked = False

        # respawn child process
        self._spawn_child_process(ChildProcess)

        return timestamps

    @property
    def primed(self):
        return self._primed
