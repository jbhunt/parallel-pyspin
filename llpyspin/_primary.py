# imports
import dill
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import MainProcess, ChildProcess
from ._recording  import VideoWriterFFmpeg, VideoWriterPySpin

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class ChildProcessPrimary(ChildProcess):
    """
    """

    def __init__(self, device):
        """
        """

        # acquisition start trigger
        self.trigger = mp.Event()

        super().__init__(device)

        return


class PrimaryCamera(MainProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        # override the child process class specification
        self._childClass = ChildProcessPrimary

        # start the child process
        self._initialize()

        # set the buffer handling mode to oldest first (instead of newest only)
        def f(obj, camera, *args, **kwargs):
            try:
                camera.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                return True
            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to set the buffer handling mode')

        #
        self._primed = False

        return

    def prime(self, filename, backend='ffmpeg'):
        """
        """

        if self.primed:
            logging.log(logging.WARNING, f'camera[{self._device}] is already primed')

        if backend not in ['ffmpeg', 'PySpin']:
            raise ValueError(f'{backend} is not a valid backend for writing video')

        def f(obj, camera, *args, **kwargs):

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

                return True

            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to prime camera[{self._device}]')
            return

        def f(obj, camera, *args, **kwargs):

            try:

                # begin acquisition
                camera.BeginAcquisition()

                # initialize the video writer
                if kwargs['backend'] == 'ffmpeg':
                    writer = VideoWriterFFmpeg().open(kwargs['filename'], kwargs['shape'], kwargs['framerate'])
                elif kwargs['backend'] == 'PySpin':
                    writer = VideoWriterPySpin().open(kwargs['filename'], kwargs['framerate'], kwargs['bitrate'])
                else:
                    return False

                # wait for the trigger event
                obj.trigger.wait()

                # unset the trigger mode
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

                # main acquisition loop
                while self.acquiring.value:

                    try:
                        result = camera.GetNextImage(1)
                    except PySpin.SpinnakerException:
                        continue

                    if not image.IsIncomplete():
                        writer.write(result)

                # reset the trigger mode
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                #
                writer.close()

                return True

            except PySpin.SpinnakerException:
                return False

        kwargs = {
            'filename'  : filename,
            'shape'     : (self.height, self.width),
            'framerate' : self.framerate,
            'bitrate'   : 1000000,
            'backend'   : 'ffmpeg'
        }
        item = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)

        #
        self._primed = True

        return

    def trigger(self):
        """
        """

        if not self._primed:
            logging.log(logging.INFO, f'camera[{self._device}] is not primed')
            return

        self._child.trigger.set()

        return

    def stop(self):
        """
        """

        if not self._primed:
            logging.log(logging.INFO, f'camera[{self._device}] is not primed')
            return

        # stop acquisition
        self._child.acquiring.value = 0

        # release the trigger (in the case of abortion before the trigger is set)
        if self._child.trigger.is_set():
            self._child.trigger.clear()

        # query the result of video acquisition
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video acquisition for camera[{self._device}] failed')

        # end acquisition and reset the camera
        def f(obj, camera, *args, **kwargs):
            try:
                camera.EndAcquisition()
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)
                camera.LineSelector.SetValue(PySpin.LineSelector_Line1)
                camera.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
                camera.LineInverter.SetValue(True)
                return True
            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video deacquisition for camera[{self._device}] failed')

        self._primed = False

        return

    def close(self):
        """
        """

        self._release()

        return

    #
    @property
    def primed(self):
        return self._primed
