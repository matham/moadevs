

__all__ = ('FTDISerializerDevice', 'FTDIPinDevice', 'FTDIADCDevice')

from moa.threads import ScheduledEventLoop
from moa.device.digital import DigitalPort
from moa.device.adc import ADCPort
from moa.logger import Logger


class FTDISerializerDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None
    ''' Because we cannot control the order in which the scheduling thread
    executes requests, during the time when a read cancel is scheduled we
    cannot add a new read request, in case the read is done before the
    scheduled cancel.
    '''

    def __init__(self, **kwargs):
        super(FTDISerializerDevice, self).__init__(cls_method=False, **kwargs)

        def write_callback(result, kw_in):
            high = kw_in['set_high']
            low = kw_in['set_low']
            attr_map = self.chan_attr_map
            self.timestamp = result

            for idx in high:
                setattr(self, attr_map[idx], True)
            for idx in low:
                setattr(self, attr_map[idx], False)
            self.dispatch('on_data_update', self)
        self.request_callback(
            name='write', callback=write_callback, trigger=False, repeat=True)

        def read_callback(result, **kwargs):
            t, val = result
            self.timestamp = t
            for idx, name in self.chan_attr_map.iteritems():
                setattr(self, name, val[idx])
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
        self.request_callback('write',
                              set_high=[attr_map[name] for name in high],
                              set_low=[attr_map[name] for name in low])

    def get_state(self):
        if self.activation != 'active':
            raise TypeError('Can only read state of an active device. Device '
                            'is currently "{}"'.format(self.activation))
        if 'i' not in self.direction:
            raise TypeError('Cannot read state for a output device')
        if self.target.continuous:
            return
        self._read_event = self.request_callback(name='read')

    def activate(self, *largs, **kwargs):
        if self.activation == 'deactivating':
            raise TypeError('Cannot activate while deactivating')
        if not super(FTDISerializerDevice, self).activate(*largs, **kwargs):
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
        if not super(FTDISerializerDevice, self).deactivate(*largs, **kwargs):
            return False
        if 'i' not in self.direction:
            self.activation = 'inactive'
            return True

        self.remove_request('read', self._read_event)
        self._read_event = None
        if self.target.settings.continuous:
            def post_cancel(result, *largs):
                self.activation = 'inactive'
            self.request_callback(
                'cancel_read', callback=post_cancel, flush=True)
        else:
            self.activation = 'inactive'
        return True


class FTDIPinDevice(ScheduledEventLoop, DigitalPort):

    _read_event = None

    def __init__(self, **kwargs):
        super(FTDIPinDevice, self).__init__(cls_method=False, **kwargs)

        def write_callback(result, kw_in):
            _, value, mask = kw_in['data'][0]
            self.timestamp = result
            for idx, name in self.chan_attr_map.iteritems():
                if mask & (1 << idx):
                    setattr(self, name, bool(value & (1 << idx)))
            self.dispatch('on_data_update', self)
        self.request_callback(
            name='write', callback=write_callback, trigger=False, repeat=True)

        def read_callback(result, **kwargs):
            t, (val, ) = result
            self.timestamp = t
            mask = self.target.settings.bitmask
            for idx, name in self.chan_attr_map.iteritems():
                if mask & (1 << idx):
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

        self.request_callback('write', data=[(1, val, mask)])

    def get_state(self):
        if self.activation != 'active':
            raise TypeError('Can only read state of an active device. Device '
                            'is currently "{}"'.format(self.activation))
        if 'i' not in self.direction:
            raise TypeError('Cannot read state for a output device')
        if self.target.continuous:
            return
        self._read_event = self.request_callback(name='read')

    def activate(self, *largs, **kwargs):
        if self.activation == 'deactivating':
            raise TypeError('Cannot activate while deactivating')
        if not super(FTDIPinDevice, self).activate(*largs, **kwargs):
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
        if not super(FTDIPinDevice, self).deactivate(*largs, **kwargs):
            return False
        if 'i' not in self.direction:
            self.activation = 'inactive'
            return True

        self.remove_request('read', self._read_event)
        self._read_event = None
        if self.target.settings.continuous:
            def post_cancel(result, *largs):
                self.activation = 'inactive'
            self.request_callback(
                'cancel_read', callback=post_cancel, flush=True)
        else:
            self.activation = 'inactive'
        return True


class FTDIADCDevice(ScheduledEventLoop, ADCPort):

    _read_event = None
    _state_event = None

    def __init__(self, **kwargs):
        super(FTDIADCDevice, self).__init__(cls_method=False, **kwargs)
        self.num_channels = 2
        self.raw_data = [None, None]
        self.data = [None, None]
        self.ts_idx = [0, 0]
        self.active_channels = [False, False]

        def read_callback(result, **kwargs):
            self.timestamp = result.ts
            self.raw_data[0] = result.chan1_raw
            self.raw_data[1] = result.chan2_raw
            self.ts_idx[0] = result.chan1_ts_idx
            self.ts_idx[1] = result.chan2_ts_idx
            self.data[0] = result.chan1_data
            self.data[1] = result.chan2_data
            self.dispatch('on_data_update', self)
        self.request_callback(
            name='read', callback=read_callback, trigger=False, repeat=True)

    def _set_state(self, *largs):
        # when active, start reading.
        self._read_event = self.request_callback(name='read', repeat=True)

    def activate(self, *largs, **kwargs):
        if self.activation == 'deactivating':
            raise TypeError('Cannot activate while deactivating')
        if not super(FTDIADCDevice, self).activate(*largs, **kwargs):
            return False
        self.activation = 'active'

        # first set state to active
        self._state_event = self.request_callback(
            name='set_state', callback=self._set_state, state=True)
        return True

    def deactivate(self, *largs, **kwargs):
        '''This device will not deactivate immediately.
        '''
        if self.activation == 'activating':
            raise TypeError('Cannot deactivate while activating')
        if not super(FTDIADCDevice, self).deactivate(*largs, **kwargs):
            return False

        self.remove_request('read', self._read_event)
        self.remove_request('set_state', self._state_event)
        self._read_event = None
        self._state_event = None

        def post_cancel(result, *largs):
            try:
                self.target.read()
                Logger.debug("I guess it didn't crash!")
            except:
                pass
            self.activation = 'inactive'
        self.request_callback('set_state', callback=post_cancel, state=False)
        return True
