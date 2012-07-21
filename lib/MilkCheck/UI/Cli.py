# Copyright CEA (2011-2012)
# Contributor: TATIBOUET Jeremie <tatibouetj@ocre.cea.fr>
# Contributor: Aurelien Cedeyn <aurelien.cedeyn@cea.fr>

'''
This module contains the UserView class definition.
'''

# classes
import fcntl, termios, struct, os
from signal import SIGINT
from sys import stdout, stderr
from ClusterShell.NodeSet import NodeSet
from MilkCheck.UI.UserView import UserView
from MilkCheck.UI.OptionParser import McOptionParser
from MilkCheck.Engine.Action import Action
from MilkCheck.Engine.Service import Service
from MilkCheck.ActionManager import action_manager_self
from MilkCheck.ServiceManager import service_manager_self
from MilkCheck.Config.ConfigParser import ConfigParser, ConfigParserError

# Exceptions
from yaml.scanner import ScannerError
from MilkCheck.ServiceManager import ServiceNotFoundError
from MilkCheck.UI.OptionParser import InvalidOptionError
from MilkCheck.Engine.BaseEntity import InvalidVariableError
from MilkCheck.Engine.BaseEntity import UndefinedVariableError
from MilkCheck.Engine.BaseEntity import VariableAlreadyReferencedError
from MilkCheck.Engine.BaseEntity import DependencyAlreadyReferenced
from MilkCheck.Engine.BaseEntity import IllegalDependencyTypeError
from MilkCheck.Engine.Service import ActionNotFoundError

# Symbols
from MilkCheck.Engine.BaseEntity import WARNING, SKIPPED
from MilkCheck.Engine.BaseEntity import TIMED_OUT, TOO_MANY_ERRORS, ERROR, DONE
from MilkCheck.UI.UserView import RC_OK, RC_EXCEPTION, RC_UNKNOWN_EXCEPTION

MAXTERMWIDTH = 120

class Terminal(object):
    '''Allow the displayer to get informations from the terminal'''

    @classmethod
    def _ioctl_gwinsz(cls, fds):
        '''Try to determine terminal width'''
        try:
            data = fcntl.ioctl(fds, termios.TIOCGWINSZ, '1234')
            crt = struct.unpack('hh', data)
        except (IOError, struct.error, ValueError):
            return None
        return crt

    @classmethod
    def size(cls):
        '''Return a tuple which contain the terminal size or default size'''
        crt = cls._ioctl_gwinsz(0) or cls._ioctl_gwinsz(1) or \
             cls._ioctl_gwinsz(2)
        if not crt:
            try:
                fds = os.open(os.ctermid(), os.O_RDONLY)
                crt = cls._ioctl_gwinsz(fds)
                os.close(fds)
            except OSError:
                pass
        if not crt:
            crt = (os.environ.get('LINES', 25), os.environ.get('COLUMNS', 80))
        return int(crt[1]), int(crt[0])

    @classmethod
    def isatty(cls):
        '''Determine if the current terminal is teletypewriter'''
        return stdout.isatty() and stderr.isatty()

class ConsoleDisplay(object):
    '''
    ConsoleDisplay provides methods allowing the CLI to print
    formatted messages on STDOUT.
    '''
    _COLORS = {
                'GREEN': '\033[0;32m%s\033[0m',
                'YELLOW': '\033[0;33m%s\033[0m',
                'RED': '\033[0;31m%s\033[0m',
                'MAGENTA': '\033[0;35m%s\033[0m',
                'CYAN': '\033[0;36m%s\033[0m'
              }
    _LARGEST_STATUS = max([len(status) \
         for status in (SKIPPED, WARNING, TIMED_OUT, TOO_MANY_ERRORS, ERROR,
                        DONE)])

    def __init__(self):
        width = Terminal.size()[0]
        # On very wide terminal, do not put the status too far away
        self._term_width = min(width, MAXTERMWIDTH)
        self._pl_width = 0
        self._color = Terminal.isatty()

    def string_color(self, strg, color):
        '''Return a string formatted with a special color'''
        if self._color:
            return '%s' % self._COLORS[color] % strg
        else:
            return '%s' % strg

    def print_running_tasks(self):
        '''Rewrite the current line and print the current running tasks'''
        rtasks = [t.parent.name for t in action_manager_self().running_tasks]
        if rtasks:
            tasks_disp = '[%s]' % ','.join(rtasks)
            width = min(self._pl_width, self._term_width)
            stdout.write('\r%s\r%s\r' % (width * ' ', tasks_disp))
            stdout.flush()
            self._pl_width = len(tasks_disp)

    def __rprint(self, line):
        '''Rewrite the current line and display line and jump to the next one'''
        width = min(self._pl_width, self._term_width)
        stderr.write('\r%s\r%s\n' % (width * ' ', line))
        self._pl_width = len(line)

    def print_status(self, entity):
        '''Remove current line and print the status of an entity onSTDOUT'''
        msg_width = self._term_width - (self._LARGEST_STATUS + 4)
        line = '%%-%ds%%%ds' % (msg_width, (self._LARGEST_STATUS + 4))
        if entity.status in (TIMED_OUT, TOO_MANY_ERRORS, ERROR):
            line = line % (entity.fullname(),
                '[%s]' % \
                    self.string_color(
                    entity.status.center(self._LARGEST_STATUS), 'RED'))
        elif entity.status in (WARNING, SKIPPED):
            line = line % (entity.fullname(),
                '[%s]' % \
                self.string_color(entity.status.center(self._LARGEST_STATUS),
                                  'YELLOW'))
        elif entity.status is DONE:
            line = line % (entity.fullname(),
                '[%s]' % \
                self.string_color('OK'.center(self._LARGEST_STATUS),
                                  'GREEN'))
        else:
            line = line % (entity.name, '[%s]' % entity.status)
        self.__rprint(line)

    def print_action_command(self, action):
        '''Remove the current line and write informations about the command'''
        target = action.resolve_property('target') or 'localhost'
        line = '%s %s %s %s\n > %s' % \
            (self.string_color(action.name, 'MAGENTA'),
             action.parent.fullname(),
             self.string_color('on', 'MAGENTA'), target,
             self.string_color(
                action.resolve_property('command'), 'CYAN'))
        self.__rprint(line)

    def __gen_action_output(self, iterbuf, iterrc, error_only):
        '''Display command result from output and retcodes.'''

        # Build the list of non-zero rc nodes
        retcodes = list(iterrc)
        ok_nodes = NodeSet.fromlist((nds for rc, nds in retcodes if rc == 0))

        output = []
        for out, nodes in iterbuf:
            if error_only:
                nodes = NodeSet(nodes) - ok_nodes
            if nodes and out:
                for lbuf in out.splitlines():
                    output.append(' > %s: %s' %
                                  (self.string_color(nodes, 'CYAN'), lbuf))

        for retcode, nodes in retcodes:
            if retcode == 0 and not error_only:
                output.append(' > %s exited with %s' %
                              (self.string_color(nodes, 'CYAN'),
                               self.string_color(retcode, 'GREEN')))
            else:
                output.append(' > %s exited with %s' %
                              (self.string_color(nodes, 'CYAN'),
                               self.string_color(retcode, 'RED')))
        return output

    def print_action_results(self, action, error_only=False):
        '''Remove the current line and write grouped results of an action'''
        line = ['%s %s ran in %.2f s' % \
            (self.string_color(action.name, 'MAGENTA'),
             action.parent.fullname(),
             action.duration)]
        # Local action
        if action.worker.current_node is None:
            line += self.__gen_action_output(
                                       [(action.worker.read(), 'localhost')],
                                       [(action.worker.retcode(),'localhost')],
                                       error_only)
        # Remote action
        else:
            line += self.__gen_action_output(action.worker.iter_buffers(),
                                             action.worker.iter_retcodes(),
                                             error_only)
        self.__rprint("\n".join(line))

    def print_delayed_action(self, action):
        '''Display a message specifying that this action has been delayed'''
        line = '%s %s %s %s s' % \
            (self.string_color(action.name, 'MAGENTA'),
             action.parent.fullname(),
             self.string_color('will fire in', 'MAGENTA'),
             action.delay)
        self.__rprint(line)

class CommandLineInterface(UserView):
    '''
    This class models the Command Line Interface which is a UserView. From
    this class you can get back events generated by the engine and send order
    to the ServiceManager.
    '''

    def __init__(self):
        UserView.__init__(self)
        # Parser which reads the command line
        self._mop = None
        # Store the options parsed
        self._options = None
        # Store the configuration parsed
        self._conf = None
        # Store the arguments parsed
        self._args = None
        # Displayer
        self._console = ConsoleDisplay()

        self._logger = ConfigParser.install_logger()

        # Profiling mode (help in unit tests)
        self.profiling = False
        # Used in profiling mode
        # Each counter match to a verbosity level
        self.count_low_verbmsg = 0
        self.count_average_verbmsg = 0
        self.count_high_verbmsg = 0

    def execute(self, command_line):
        '''
        Ask for the manager to execute orders given by the command line.
        '''
        self._mop = McOptionParser()
        self._mop.configure_mop()
        self.count_low_verbmsg = 0
        self.count_average_verbmsg = 0
        self.count_high_verbmsg = 0
        retcode = RC_OK
        try:
            (self._options, self._args) = self._mop.parse_args(command_line)

            self._conf = ConfigParser(self._options)

            manager = service_manager_self()
            # Case 1 : call services referenced in the manager with
            # the required action
            if self._args:
                # Compute all services with the required action
                services = self._args[:-1]
                action = self._args[-1]
                retcode = manager.call_services(services, action,
                                                conf=self._conf)
            # Case 2 : Check configuration
            elif self._conf['config_dir']:
                print "No actions specified, checking configuration..."
                manager.load_config(self._conf['config_dir'])
                print "%s seems good" % self._conf['config_dir']
            # Case 3: Nothing to do so just print MilkCheck help
            else:
                self._mop.print_help()
        except (ServiceNotFoundError, 
                ActionNotFoundError,
                InvalidVariableError,
                UndefinedVariableError,
                VariableAlreadyReferencedError,
                DependencyAlreadyReferenced,
                IllegalDependencyTypeError,
                ConfigParserError,
                ScannerError), exc:
            self._logger.error(str(exc))
            return RC_EXCEPTION
        except InvalidOptionError, exc:
            self._logger.error(str(exc))
            self._mop.print_help()
            return RC_EXCEPTION
        except KeyboardInterrupt, exc:
            self._logger.error('Keyboard Interrupt')
            return (128 + SIGINT)
        except ScannerError, exc:
            self._logger.error('Bad syntax in config file :\n%s' % exc)
            return RC_EXCEPTION
        except Exception, exc:
            # In debug mode, propagate the error
            if (not self._conf or self._conf.get('debug')):
                raise
            else:
                self._logger.error('Unexpected Exception : %s' % exc)
            return RC_UNKNOWN_EXCEPTION
        return retcode

    def ev_started(self, obj):
        '''
        Something has started on the object given as parameter. This migh be
        the beginning of a command one a node, an action or a service.
        '''
        if isinstance(obj, Action) and self._conf['verbosity'] >= 2:
            self._console.print_action_command(obj)
            self._console.print_running_tasks()
            if self.profiling:
                self.count_average_verbmsg += 1
        elif isinstance(obj, Service) and self._conf['verbosity'] >= 1:
            self._console.print_running_tasks()
            if self.profiling:
                self.count_low_verbmsg += 1

    def ev_complete(self, obj):
        '''
        Something is complete on the object given as parameter. This migh be
        the end of a command on a node,  an action or a service.
        '''
        if isinstance(obj, Action) and self._conf['verbosity'] >= 3 and \
            obj.status != SKIPPED:
            self._console.print_action_results(obj)
            self._console.print_running_tasks()
            if self.profiling:
                self.count_high_verbmsg += 1
        elif isinstance(obj, Action) and \
            obj.status in (TIMED_OUT, TOO_MANY_ERRORS, ERROR) and \
                 self._conf['verbosity'] >= 1:
            self._console.print_action_results(obj, 
                                               self._conf['verbosity'] == 1)
            self._console.print_running_tasks()
            if self.profiling:
                self.count_average_verbmsg += 1
        elif isinstance(obj, Service) and self._conf['verbosity'] >= 1:
            self._console.print_running_tasks()
            if self.profiling:
                self.count_low_verbmsg += 1

    def ev_status_changed(self, obj):
        '''
        Status of the object given as parameter. Actions or Service's status
        might have changed.
        '''
        if isinstance(obj, Service) and self._conf['verbosity'] >= 1 and \
            not (obj.status == SKIPPED and self._options.verbosity < 3) and \
            obj.status in (TIMED_OUT, TOO_MANY_ERRORS, ERROR, DONE,
                           WARNING, SKIPPED) and not obj.simulate:

            self._console.print_status(obj)
            self._console.print_running_tasks()
            if self.profiling:
                self.count_low_verbmsg += 1

    def ev_delayed(self, obj):
        '''
        Object given as parameter has been delayed. This event is only raised
        when an action was delayed
        '''
        if isinstance(obj, Action) and self._conf['verbosity'] >= 3:
            self._console.print_delayed_action(obj)
            self._console.print_running_tasks()
            if self.profiling:
                self.count_average_verbmsg += 1

    def ev_trigger_dep(self, obj_source, obj_triggered):
        '''
        obj_source/obj_triggered might be an action or a service. This
        event is raised when the obj_source triggered another object. Sample :
        Action A triggers Action B
        Service A triggers Service B
        '''
        pass

    def get_totalmsg_count(self):
        '''Sum all counter to know how many message the CLI got'''
        return  (self.count_low_verbmsg + \
                    self.count_average_verbmsg + \
                        self.count_high_verbmsg)

    total_msg_count = property(fget=get_totalmsg_count)
