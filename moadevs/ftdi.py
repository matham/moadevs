

__all__ = ('FTDISerializerDevice', 'FTDIPinDevice')

from moa.threads import ScheduledEventLoop
from moa.device.gate import DigitalPort


class FTDISerializerDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None
    _canceling = False
    ''' Because we cannot control the order in which the scheduling thread
    executes requests, during the time when a read cancel is scheduled we
    cannot add a new read request, in case the read is done before the
    scheduled cancel.
    '''

    def __init__(self, **kwargs):
        super(FTDISerializerDevice, self).__init__(**kwargs)

        def write_callback(result, kw_in):
            high = kw_in['set_high']
            low = kw_in['set_low']
            mapping = self._inverse_map
            self.timestamp = result

            for idx in high:
                setattr(self, mapping[idx], True)
            for idx in low:
                setattr(self, mapping[idx], False)
        self.request_callback(name='write', callback=write_callback,
                              trigger=False, repeat=True, unique=False)

        def read_callback(result, **kwargs):
            t, val = result
            self.timestamp = t
            for idx, name in self._inverse_map.iteritems():
                setattr(self, name, val[idx])
        self.request_callback(name='read', callback=read_callback,
                              trigger=False, repeat=True, unique=False)

    def set_state(self, high=[], low=[], **kwargs):
        mapping = self.mapping
        self.request_callback('write', callback=None,
                              set_high=[mapping[name] for name in high],
                              set_low=[mapping[name] for name in low])

    def activate(self, *largs, **kwargs):
        if not super(FTDISerializerDevice, self).activate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self._read_event = self.request_callback(name='read', repeat=True)
        return True

    def deactivate(self, *largs, **kwargs):
        if not super(FTDISerializerDevice, self).deactivate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self.remove_request('read', self._read_event)
        self._read_event = None
        if self.target.settings.continuous:
            self._canceling = True

            def post_cancel(result, *kw):
                self._canceling = False
                if self.input and len(self._activated_set):
                    self._read_event = self.request_callback(name='read',
                        repeat=True)
            self.request_callback('cancel_read', callback=post_cancel,
                                  flush=True)
        return True


class FTDIPinDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None
    _canceling = False

    def __init__(self, **kwargs):
        super(FTDIPinDevice, self).__init__(**kwargs)

        def write_callback(result, kw_in):
            _, value, mask = kw_in['data'][0]
            self.timestamp = result
            for idx, name in self._inverse_map.iteritems():
                if mask & (1 << idx):
                    setattr(self, name, bool(value & (1 << idx)))
        self.request_callback(name='write', callback=write_callback,
                              trigger=False, repeat=True, unique=False)

        def read_callback(result, **kwargs):
            t, (val, ) = result
            self.timestamp = t
            mask = self.target.settings.bitmask
            for idx, name in self._inverse_map.iteritems():
                if mask & (1 << idx):
                    setattr(self, name, bool(val & (1 << idx)))
        self.request_callback(name='read', callback=read_callback,
                              trigger=False, repeat=True, unique=False)

    def set_state(self, high=[], low=[], **kwargs):
        mapping = self.mapping
        mask = 0
        val = 0
        for name in high:
            idx = mapping[name]
            val |= (1 << idx)
            mask |= (1 << idx)
        for name in low:
            mask |= (1 << mapping[name])

        self.request_callback('write', callback=lambda *x: 10, data=[(1, val, mask)])

    def activate(self, *largs, **kwargs):
        if not super(FTDIPinDevice, self).activate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self._read_event = self.request_callback(name='read', repeat=True)
        return True

    def deactivate(self, *largs, **kwargs):
        if not super(FTDIPinDevice, self).deactivate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self.remove_request('read', self._read_event)
        self._read_event = None
        if self.target.settings.continuous:
            self._canceling = True

            def post_cancel(result, *kw):
                self._canceling = False
                if self.input and len(self._activated_set):
                    self._read_event = self.request_callback(name='read',
                        repeat=True)
            self.request_callback('cancel_read', flush=True)
        return True
