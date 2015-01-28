

__all__ = ('MCDAQDevice', )


from moa.threads import ScheduledEventLoop
from moa.device.digital import DigitalPort


class MCDAQDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None

    def __init__(self, **kwargs):
        super(MCDAQDevice, self).__init__(cls_method=False, **kwargs)

        def write_callback(result, kw_in):
            value = kw_in['value']
            mask = kw_in['mask']
            self.timestamp = result
            for idx, name in self.chan_attr_map.iteritems():
                if mask & (1 << idx):
                    setattr(self, name, bool(value & (1 << idx)))
            self.dispatch('on_data_update', self)
        self.request_callback(
            name='write', callback=write_callback, trigger=False, repeat=True)

        def read_callback(result, **kwargs):
            t, val = result
            self.timestamp = t
            for idx, name in self.chan_attr_map.iteritems():
                setattr(self, name, bool(val & (1 << idx)))
            self.dispatch('on_data_update', self)
        self.request_callback(
            name='read', callback=read_callback, trigger=False, repeat=True)

    def set_state(self, high=[], low=[], **kwargs):
        if self.activation != 'active':
            raise TypeError('Can only set state of an active device. Device '
                            'is currently "{}"'.format(self.activation))
        if 'o' not in self.direction:
            raise TypeError('Cannot write state for a input device')
        attr_map = self.attr_map
        mask = 0
        val = 0
        for name in high:
            idx = attr_map[name]
            val |= (1 << idx)
            mask |= (1 << idx)
        for name in low:
            mask |= (1 << attr_map[name])

        self.request_callback('write', mask=mask, value=val)

    def get_state(self):
        if self.activation != 'active':
            raise TypeError('Can only read state of an active device. Device '
                            'is currently "{}"'.format(self.activation))
        if 'i' in self.direction and self.target.continuous:
            return
        self._read_event = self.request_callback(name='read')

    def activate(self, *largs, **kwargs):
        if self.activation == 'deactivating':
            raise TypeError('Cannot activate while deactivating')
        if not super(MCDAQDevice, self).activate(*largs, **kwargs):
            return False
        self.activation = 'active'

        if 'i' in self.direction and self.target.continuous:
            self._read_event = self.request_callback(name='read', repeat=True)
        return True

    def deactivate(self, *largs, **kwargs):
        '''This device may not deactivate immediately.
        '''
        if self.activation == 'activating':
            raise TypeError('Cannot deactivate while activating')
        if not super(MCDAQDevice, self).deactivate(*largs, **kwargs):
            return False

        self.remove_request('read', self._read_event)
        self._read_event = None
        if 'i' in self.direction and self.target.continuous:
            def post_cancel(result, *largs):
                self.activation = 'inactive'
            self.request_callback('cancel_read', callback=post_cancel,
                                  flush=True)
        else:
            self.activation = 'inactive'
        return True
