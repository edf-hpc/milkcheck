#
# Copyright CEA (2011-2012)
#
# This file is part of MilkCheck project.
#
# This software is governed by the CeCILL license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".
#
# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.
#
# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.
#
# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.

'''
This module contains the definiton of both CallbackHandler and
CoreEvent.
'''

EV_STATUS_CHANGED = 'EV_STATUS_CHANGED'
EV_STARTED = 'EV_STARTED'
EV_COMPLETE = 'EV_COMPLETE'
EV_FINISHED = 'EV_FINISHED'
EV_DELAYED = 'EV_DELAYED'
EV_TRIGGER_DEP = 'EV_TRIGGER_DEP'

class CallbackHandler(object):
    '''
    This class is a singleton. It registers the interface elements (console,
    gui, filewriter, etc) which want to receive notifications from the core
    engine. In order to be registred those elements have to implements the
    interface EngineNotification (or inherit from class which implements it).
    '''

    _instance = None

    def __init__(self):
        # interfaces that have to be notified
        self._interfaces = set()

    def attach(self, interface):
        '''Attach an interface to the callback handler'''
        assert interface, 'interface attached cannot be None'
        self._interfaces.add(interface)

    def detach(self, interface):
        '''Detach an interface from the callback handler'''
        assert interface, 'interface detached cannot be None'
        if interface in self._interfaces:
            self._interfaces.remove(interface)

    def notify(self, obj, ev_name):
        '''Notify the interfaces registered within the callback handler'''
        for interface in self._interfaces:
            if ev_name is EV_STATUS_CHANGED:
                interface.ev_status_changed(obj)
            elif ev_name is EV_STARTED:
                interface.ev_started(obj)
            elif ev_name is EV_COMPLETE:
                interface.ev_complete(obj)
            elif ev_name is EV_FINISHED:
                interface.ev_finished(obj)
            elif ev_name is EV_TRIGGER_DEP:
                assert isinstance(obj, tuple)
                (source, target) = obj
                interface.ev_trigger_dep(source, target)
            else:
                interface.ev_delayed(obj)

def call_back_self():
    """Return a singleton instance of the CallbackHandler class"""
    if not CallbackHandler._instance:
        CallbackHandler._instance = CallbackHandler()
    return CallbackHandler._instance

class CoreEvent(object):
    '''
    This interface specifies the protoypes of events generated by the core
    of MilkCheck. Those events have to implemented by child classes. CoreEvent
    provide a read_only access from the UI to the Engine.
    '''
    def ev_started(self, obj):
        '''
        Something has started on the object given as parameter. This migh be
        the beginning of a command one a node, an action or a service.
        '''
        raise NotImplementedError

    def ev_complete(self, obj):
        '''
        Something is complete on the object given as parameter. This migh be
        the end of a command on a node,  an action or a service.
        '''
        raise NotImplementedError

    def ev_finished(self, obj):
        '''All tasks are done.'''
        raise NotImplementedError

    def ev_status_changed(self, obj):
        '''
        Status of the object given as parameter. Actions or Service's status
        might have changed.
        '''
        raise NotImplementedError
        
    def ev_delayed(self, obj):
        '''
        Object given as parameter has been delayed. This event is only raised
        when an action was delayed
        '''
        raise NotImplementedError

    def ev_trigger_dep(self, obj_source, obj_triggered):
        '''
        obj_source/obj_triggered might be an action or a service. This
        event is raised when the obj_source triggered another object. Sample :
        Action A triggers Action B
        Service A triggers Service B
        '''
        raise NotImplementedError
