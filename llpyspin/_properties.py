import logging
import numpy as np

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class AcquisitionProperty(object):
    """
    a minimal implementation of descriptors with the additional functionality
    to handle intermitent interruption of acquisition during changes in property
    values

    references
    ----------
    [1] https://docs.python.org/3/howto/descriptor.html#properties
    """


    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget   = fget
        self.fset   = fset
        self.fdel   = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

        # internal flag that records the state of camera acquisition
        self._paused = False

        return

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError('unreadable attribute')
        return self.fget(obj)

    def _pause(self, obj):
        """
        pause acquisition
        """

        logging.debug('pausing acquisition')

        # check the result of the call to start video acquisition
        obj.acquiring = False
        if obj._result == False:
            logging.debug('video acquisition failed')

        # make a call to stop video acquisition
        obj._iq.put('stop')
        if obj._result == False:
            logging.debug('video de-acquisition failed')

        # set the paused flag
        self._paused = True

        return

    def _resume(self, obj):
        """
        resume acquisition
        """

        logging.debug('resuming acquisition')

        # set the acquisition flag to True
        obj.acquiring = True

        # start the acquisition
        obj._iq.put('start')

        # un-set the paused flag
        self._paused = False

        return

    def __set__(self, obj, value):
        """
        """

        if self.fset is None:
            raise AttributeError("attribute is read-only")

        # check acquisition lock
        if obj.locked:
            raise Exception('acquisition lock is engaged')

        # pause acquisition
        if obj.acquiring:
            self._pause(obj)

        # call the fset method
        self.fset(obj, value)

        # resume acquisition
        if self._paused:
            self._resume(obj)

        return

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.__doc__)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.__doc__)

class PropertiesMixin(object):
    """
    This mixin contains all the video acquisition property definitions.
    """

    @property
    def settings(self):
        """
        print the current values for all modifiable acquisition properties
        """

        info = [
        f'framerate : {self.framerate} fps',
        f'exposure  : {self.exposure} us',
        f'binsize   : {self.binsize} pixel(s)',
        f'roi       : {self.roi}'
        ]

        for line in info: print(line)

    # framerate
    @AcquisitionProperty
    def framerate(self): return self._framerate

    @framerate.setter
    def framerate(self, value):
        """
        """

        # the default value is 30 fps
        if value == None:
            level = logging.DEBUG
            value = 30

        else:
            level = logging.INFO

        #
        self._iq.put('set')
        self._iq.put(['framerate', value])

        #
        if self._result == False:
            logging.info(f'failed to set the framerate to {value} fps')
            return

        logging.log(level, f'framerate set to {value} fps')

        self._framerate = value

        return

    # exposure
    @AcquisitionProperty
    def exposure(self): return self._exposure

    @exposure.setter
    def exposure(self, value):
        """
        """

        # default value is 1500 us
        if value == None:
            level = logging.DEBUG
            value = 1500

        else:
            level = logging.INFO

        # input
        self._iq.put('set')
        self._iq.put(['exposure', value])

        if self._result == False:
            logging.info(f'failed to set the exposure to {value} us')
            return

        logging.log(level, f'exposure set to {value} us')

        self._exposure = value

        return

    # binsize
    @AcquisitionProperty
    def binsize(self): return self._binsize

    @binsize.setter
    def binsize(self, value):
        """
        """

        # default binsize is 2 pixels
        if value == None:
            level = logging.DEBUG
            value = 2

        else:
            level = logging.INFO

        # input
        self._iq.put('set')
        self._iq.put(['binsize', value])

        #
        if self._result == False:
            logging.info(f'failed to set the binsize to {value} pixel(s)')
            return

        logging.log(level, f'binsize set to {value} pixel(s)')

        self._binsize = value

        # reset the ROI as changing the binsize invalidates the ROI parameters
        self.roi = None

        # decreasing binsize might decrease the camera's maximum framerate
        # make sure the current framerate is compatible with the new binsize

        self._iq.put('get')
        self._iq.put(['framerate', 'maximum'])

        value  = self._oq.get()
        result = self._oq.get()

        if self.framerate > value:
            value = int(np.floor(value))
            self.framerate = value

        return

    @AcquisitionProperty
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        """
        """

        # reset the ROI
        if value == None:

            level = logging.DEBUG # change the logging level

            # re-zero the offset
            self._iq.put('set')
            self._iq.put(['offset', (0, 0)])
            if self._result == False: pass

            # get maximum width
            self._iq.put('get')
            self._iq.put(['width', 'maximum'])
            width = self._oq.get()
            if self._result == False: pass

            # get maximum height
            self._iq.put('get')
            self._iq.put(['height', 'maximum'])
            height = self._oq.get()
            if self._result == False: pass

            # reset the shape of the video frame
            self._iq.put('set')
            self._iq.put(['shape', (height, width)])
            if self._result == False: pass

            self._roi = (0, 0, height, width)

            return

        # make sure the parameters are integers
        else:
            value = tuple(map(int, value))
            level = logging.INFO

        # set the new roi
        self._iq.put('set')
        self._iq.put(['roi', value])

        if self._result == False:
            logging.error(f'failed to set the ROI parameters to {value}')
            return

        logging.log(level, f'ROI parameters set to {value}')

        self._roi = value
