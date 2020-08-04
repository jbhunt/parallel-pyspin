import logging

# constants
from ._constants import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.DEBUG)

class AcquisitionProperty(object):
    """
    a pure Python implementation of properties with the additional functionality
    to check that the value of the property to-set passes a check defined by the
    checker method, i.e., the call to the property's __set__ method is dependent
    upon the result of the call to the __check__ method.

    notes
    -----
    An instance of this class will function exactly like a property unless the
    'checker' method is defined via decoration.

    references
    ----------
    [1] https://docs.python.org/3/howto/descriptor.html#properties
    """

    def __init__(self, fget=None, fset=None, fdel=None, fcheck=None, doc=None):
        self.fget   = fget
        self.fset   = fset
        self.fdel   = fdel
        self.fcheck = fcheck
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj, value):
        """
        """

        if self.fset is None:
            raise AttributeError("can't set attribute")

        # perform the check
        result = self.__check__(obj, value)

        # check passed
        if result:

            # pause acquiition
            try: assert obj.acquiring == False; restart = False
            except AssertionError:
                logging.debug('Pausing acquisition.')
                obj.acquiring = False
                result = obj._oq.get()
                if not result: logging.debug('Video acquisition failed.')
                obj._iq.put(STOP)
                result = obj._oq.get()
                if not result: logging.debug('Video de-acquisition failed')
                restart = True

            # call the fset method
            self.fset(obj, value)

            # restart acquisition
            if restart:
                logging.debug('Unpausing acquisition.')
                obj.acquiring = True
                obj._iq.put(START)

        # check failed
        else:
            raise ValueError("value to-set did not pass check")

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def __check__(self, obj, value):
        if self.fcheck is None:
            return True # passes the check unless fcheck is defined
        return self.fcheck(obj, value)

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.fcheck, self.__doc__)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.fcheck, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.fcheck, self.__doc__)

    def checker(self, fcheck):
        return type(self)(self.fget, self.fset, self.fdel, fcheck, self.__doc__)

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

        return

    # framerate property
    @AcquisitionProperty
    def framerate(self): return self._framerate

    @framerate.checker
    def framerate(self, value):
        try:
            assert FRAMERATE_MINIMUM_VALUE <= value <= FRAMERATE_MAXIMUM_VALUE
            assert type(value) == FRAMERATE_PROPERTY_TYPE
            result = True

        except AssertionError:
            result = False

        return result

    @framerate.setter
    def framerate(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(FRAMERATE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'Setting framerate to {value} fps.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the framerate to "{value}" fps.')
            return

        self._framerate = value

        return

    # exposure
    @AcquisitionProperty
    def exposure(self): return self._exposure

    @exposure.checker
    def exposure(self, value):
        try:
            assert EXPOSURE_MINIMUM_VALUE <= value <= EXPOSURE_MAXIMUM_VALUE
            assert type(value) == EXPOSURE_PROPERTY_TYPE
            result = True

        except AssertionError:
            result = False

        return result

    @exposure.setter
    def exposure(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(EXPOSURE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'Setting exposure to {value} us.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the exposure to "{value}" us.')
            return

        self._exposure = value
        return

    # binsize
    @AcquisitionProperty
    def binsize(self): return self._binsize

    @binsize.checker
    def binsize(self, value):
        try:
            assert BINSIZE_MINIMUM_VALUE <= value <= BINSIZE_MAXIMUM_VALUE
            assert type(value) == BINSIZE_PROPERTY_TYPE
            assert value != BINSIZE_INVALID_VALUE
            result = True

        except AssertionError:
            result = False

        return result

    @binsize.setter
    def binsize(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(BINSIZE_PROPERTY_ID)
        self._iq.put(value)

        logging.info(f'Setting binsize to {value} pixels.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the binsize to "{value}" pixel(s).')
            return

        self._binsize = value

        return
