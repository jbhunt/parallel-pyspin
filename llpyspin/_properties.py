import logging

# constants
from ._constants import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.DEBUG)

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

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def pause(self, obj):
        """
        """

        if not obj.acquiring:
            return False

        logging.debug('pausing acquisition')

        #
        obj.acquiring = False
        result = obj._oq.get()
        if not result:
            logging.debug('video acquisition failed')

        #
        obj._iq.put(STOP)
        result = obj._oq.get()
        if not result:
            logging.debug('video de-acquisition failed')

        return True

    def resume(self, obj):
        """
        """

        logging.debug('resuming acquisition.')

        # set the acquisition flag to True
        obj.acquiring = True

        # start the acquisition
        obj._iq.put(START)

        return

    def lock(self, obj):
        """
        """

        if hasattr(obj,'_lock'):
            result = obj._lock.acquire(block=False)
            if not result:
                raise Exception('acquisition lock is engaged')

        return

    def unlock(self, obj):
        """
        """

        if hasattr(obj,'_lock'):

            try:
                obj._lock.release()

            # this happens if the lock is released manually in the property's setter method
            except ValueError:
                logging.debug('acquisition lock released more than once')
                pass

        return

    def __set__(self, obj, value):
        """
        """

        if self.fset is None:
            raise AttributeError("can't set attribute")

        # acquire acquisition lock
        self.lock(obj)

        # pause ongoing acquisition
        restart = self.pause(obj)

        # call the fset method
        self.fset(obj, value)

        # restart acquisition
        if restart:
            self.resume(obj)

        # release acquisition lock
        self.unlock(obj)

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

    def _setall(self):
        """
        set all properties to their current values
        """

        self.framerate = self._framerate
        self.exposure  = self._exposure
        self.binsize   = self._binsize
        self.roi       = self._roi

        return

    # framerate property
    @AcquisitionProperty
    def framerate(self): return self._framerate

    @framerate.setter
    def framerate(self, value):
        """
        """

        if value is None:

            logging.debug('setting framerate to maximum value')

            # retreive max framerate for current camera settings
            self._iq.put(GET)
            self._iq.put(FRAMERATE_PROPERTY_ID)
            value = self._oq.get()
            result = self._oq.get()
            if not result:
                logging.error(f'failed to retreive maximum framerate value')
                return

        self._iq.put(SET)
        self._iq.put(FRAMERATE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'setting framerate to {value} fps')

        result = self._oq.get()
        if not result:
            logging.warning(f'failed to set the framerate to {value} fps')
            return

        self._framerate = value

        return

    # exposure
    @AcquisitionProperty
    def exposure(self): return self._exposure

    @exposure.setter
    def exposure(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(EXPOSURE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'setting exposure to {value} us')

        result = self._oq.get()
        if not result:
            logging.warning(f'failed to set the exposure to {value} us')
            return

        self._exposure = value

        return

    # binsize
    @AcquisitionProperty
    def binsize(self): return self._binsize

    @binsize.setter
    def binsize(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(BINSIZE_PROPERTY_ID)
        self._iq.put(value)

        logging.info(f'setting binsize to {value} pixel(s)')

        result = self._oq.get()
        if not result:
            logging.warning(f'failed to set the binsize to {value} pixel(s)')
            return

        self._binsize = value

        # NOTE : to reset the ROI parameters the acquisition lock needs to be
        #        released here because the lock is acquired inside the
        #        descriptor's __set__ method to avoid changing the value of
        #        properties during video acquisition (see the descriptor's class
        #        definition)

        if hasattr(self,'_lock'):
            self._lock.release()

        # reset the ROI as changing the binsize invalidates the ROI parameters
        self.roi = None

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

            logging.debug('resetting the ROI')
            level = logging.DEBUG # change the logging level

            # get width
            self._iq.put(GET)
            self._iq.put(WIDTH_PROPERTY_ID)
            width = self._oq.get()
            result = self._oq.get()

            # get height
            self._iq.put(GET)
            self._iq.put(HEIGHT_PROPERTY_ID)
            height = self._oq.get()
            result = self._oq.get()

            value = (0, 0, height, width)

        # make sure the parameters are integers
        else:
            value = tuple(map(int, value))
            level = logging.INFO

        self._iq.put(SET)
        self._iq.put(ROI_PROPERTY_ID)
        self._iq.put(value)

        logging.log(level, f'setting the ROI parameters to {value}.')

        result = self._oq.get()
        if not result:
            logging.warning(f'failed to set the ROI parameters to {value}')
            return

        self._roi = value
