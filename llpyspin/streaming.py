import dill
import queue
import PySpin
import numpy as np
import multiprocessing as mp

# relative imports
from .dummy import DummyCameraPointer
from .processes  import MainProcess, ChildProcess, CameraError, queued, GETBY_DEVICE_INDEX


def _acquire(child, pointer, **kwargs):
    """
    Main aquisition loop
    """

    #
    dummy = True if isinstance(pointer, DummyCameraPointer) else False

    try:
        pointer.BeginAcquisition()

        # main acquisition loop
        while child.acquiring.value:

            try:
                image = pointer.GetNextImage(kwargs['timeout'])

                #
                if not image.IsIncomplete():

                    # store the image (critical - use lock)
                    with child.qlock:

                        # remove the previous image
                        if child.buffer.qsize() > 0:
                            previous = child.buffer.get()

                        # replace with the current image
                        child.buffer.put(image.GetNDArray().astype(np.uint8))

            except PySpin.SpinnakerException:
                continue

        pointer.EndAcquisition()

        return True, None, None

    except PySpin.SpinnakerException:
       return False, None, f'Video acquisition failed'

def _update_property_value(fset, value, main):
    """
    Update the value of an acquisition property without closing and reopening
    the video stream

    Notes
    -----
    This function wraps an acquisition property's setter method (see below)
    """

    # pause acquisition
    if main._child.acquiring.value == 1:
        main._child.acquiring.value = 0
        try:
            result, output, message = main._child.oq.get(timeout=3)
        except (mp.TimeoutError, queue.Empty):
            import pdb; pdb.set_trace()

    # unlock the camera
    main._locked = False

    # set the new value
    fset(main, value)

    #unpause acquisition
    main._child.acquiring.value = 1
    kwargs = {
        'shape'   : (main.width, main.height),
        'timeout' : 1
    }
    item = (dill.dumps(_acquire), kwargs)
    main._child.iq.put(item)

    # re-engage the lock
    main._locked = True

    return

#
class StreamingChildProcess(ChildProcess):
    """
    """

    def __init__(self, value=0, getby=GETBY_DEVICE_INDEX):
        """
        """

        #
        super().__init__(value, getby)

        # This queue acts as a buffer holding a single image
        self.buffer = mp.Queue()

        # This lock prevents reading and writing to the buffer at the same time
        self.qlock = mp.Lock()

        return

class VideoStream(MainProcess):
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
        self.open()

        return

    def open(self):
        """
        """

        # spawn a child process as needed
        if self._child is None:
            self._spawn_child_process(StreamingChildProcess)
        else:
            raise CameraError('Video stream is already opened')

        # set the acquisition flag
        self._child.acquiring.value = 1

        # pack the kwargs
        kwargs = {
            'shape'   : (self.width, self.height),
            'timeout' : 1
        }
        item = (dill.dumps(_acquire), kwargs)
        self._child.iq.put(item)
        self._locked = True

        return

    def close(self):
        """
        """

        # return if there is no active child or the stream is already closed
        if self._child is None:
            raise CameraError('Video stream is already closed')

        # unset the acquisition flag
        self._child.acquiring.value = 0

        # check the result of video acquisition
        result, output, message = self._child.oq.get()
        if not result:
            raise CameraError(message)

        @queued
        def f(child, pointer, **kwargs):
            try:
                if pointer.IsStreaming():
                    pointer.EndAcquisition()
                if pointer.IsInitialized():
                    pointer.DeInit()
                return True, None, None
            except PySpin.SpinnakerException:
                return False, None, f'Failed to deinitialize the camera'

        # check the result
        result, output, message = f(main=self)

        # release the acquisition lock
        self._locked = False

        # flush the buffer and clean up
        while self._child.buffer.qsize() != 0:
            discard = self._child.buffer.get()
        self._child.buffer.close()
        self._child.buffer.join_thread()

        # join the child process
        self._join_child_process()

        return

    def read(self):
        """
        """

        # return if there is no active child or the stream is closed
        if self._child is None:
            raise CameraError('Video stream is closed')

        # grab the image most recently buffered image
        try:
            with self._child.qlock:
                image = self._child.buffer.get()
            return (True, image)

        except:
            return (False, None)

    # override all of the acquisition property's setter methods
    @MainProcess.framerate.setter
    def framerate(self, value):
        _update_property_value(MainProcess.framerate.fset, value, self)

    @MainProcess.exposure.setter
    def exposure(self, value):
        _update_property_value(MainProcess.exposure.fset, value, self)

    @MainProcess.binsize.setter
    def binsize(self, value):
        _update_property_value(MainProcess.binsize.fset, value, self)

    @MainProcess.roi.setter
    def roi(self, value):
        _update_property_value(MainProcess.roi.fset, value, self)

    @MainProcess.color.setter
    def color(self, value):
        _update_property_value(MainProcess.color.fset, value, self)
