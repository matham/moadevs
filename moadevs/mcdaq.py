

__all__ = ('MCDAQDevice', )


from moa.threads import ScheduledEventLoop
from moa.device.digital import DigitalPort


class MCDAQDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None
    _canceling = False

    def __init__(self, **kwargs):
        super(MCDAQDevice, self).__init__(**kwargs)

        def write_callback(result, kw_in):
            value = kw_in['value']
            mask = kw_in['mask']
            self.timestamp = result
            for idx, name in self._inverse_map.iteritems():
                if mask & (1 << idx):
                    setattr(self, name, bool(value & (1 << idx)))
        self.request_callback(name='write', callback=write_callback,
                              trigger=False, repeat=True, unique=False)

        def read_callback(result, **kwargs):
            t, val = result
            self.timestamp = t
            for idx, name in self._inverse_map.iteritems():
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

        self.request_callback('write', callback=None, mask=mask, value=val)

    def activate(self, *largs, **kwargs):
        if not super(MCDAQDevice, self).activate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self._read_event = self.request_callback(name='read', repeat=True)
        return True

    def deactivate(self, *largs, **kwargs):
        if not super(MCDAQDevice, self).deactivate(*largs, **kwargs):
            return False
        if not self.input or self._canceling:
            return True

        self.remove_request('read', self._read_event)
        self._read_event = None
        if self.target.continuous:
            self._canceling = True

            def post_cancel(result, *kw):
                self._canceling = False
                if self.input and len(self._activated_set):
                    self._read_event = self.request_callback(name='read',
                                                             repeat=True)
            self.request_callback('cancel_read', callback=post_cancel,
                                  flush=True)
        return True
