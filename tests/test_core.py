try:
    from builtins import object
except ImportError:
    pass

import sys
from typing import TYPE_CHECKING, List
from functools import partial
from unittest import TestCase, skipIf
import weakref

from transitions import Machine, MachineError, State, EventData
from transitions.core import listify, _prep_ordered_arg, Transition

from .utils import InheritedStuff
from .utils import Stuff, DummyModel


try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import MagicMock  # type: ignore

if TYPE_CHECKING:
    from typing import Sequence
    from transitions.core import TransitionConfig, StateConfig, TransitionConfigDict


def on_exit_A(event):
    event.model.exit_A_called = True


def on_exit_B(event):
    event.model.exit_B_called = True


class TestTransitions(TestCase):

    def setUp(self):
        self.stuff = Stuff()
        self.machine_cls = Machine

    def tearDown(self):
        pass

    def test_init_machine_with_hella_arguments(self):
        states = [
            State('State1'),
            'State2',
            {
                'name': 'State3',
                'on_enter': 'hello_world'
            }
        ]
        transitions = [
            {'trigger': 'advance',
                'source': 'State2',
                'dest': 'State3'
             }
        ]
        s = Stuff()
        m = s.machine_cls(model=s, states=states, transitions=transitions, initial='State2')
        s.advance()
        self.assertEqual(s.message, 'Hello World!')

    def test_listify(self):
        self.assertEqual(listify(4), [4])
        self.assertEqual(listify(None), [])
        self.assertEqual(listify((4, 5)), (4, 5))
        self.assertEqual(listify([1, 3]), [1, 3])

        class Foo:
            pass
        obj = Foo()
        proxy = weakref.proxy(obj)
        del obj
        self.assertEqual(listify(proxy), [proxy])

    def test_weakproxy_model(self):
        d = DummyModel()
        pr = weakref.proxy(d)
        self.machine_cls(pr, states=['A', 'B'], transitions=[['go', 'A', 'B']], initial='A')
        pr.go()
        self.assertTrue(pr.is_B())

    def test_property_initial(self):
        states = ['A', 'B', 'C', 'D']
        # Define with list of dictionaries
        transitions = [
            {'trigger': 'walk', 'source': 'A', 'dest': 'B'},
            {'trigger': 'run', 'source': 'B', 'dest': 'C'},
            {'trigger': 'sprint', 'source': 'C', 'dest': 'D'}
        ]
        m = self.stuff.machine_cls(states=states, transitions=transitions, initial='A')
        self.assertEqual(m.initial, 'A')
        m = self.stuff.machine_cls(states=states, transitions=transitions, initial='C')
        self.assertEqual(m.initial, 'C')
        m = self.stuff.machine_cls(states=states, transitions=transitions)
        self.assertEqual(m.initial, 'initial')

    def test_transition_definitions(self):
        states = ['A', 'B', 'C', 'D']
        # Define with list of dictionaries
        transitions = [
            {'trigger': 'walk', 'source': 'A', 'dest': 'B'},
            {'trigger': 'run', 'source': 'B', 'dest': 'C'},
            {'trigger': 'sprint', 'source': 'C', 'dest': 'D'}
        ]  # type: Sequence[TransitionConfig]
        m = Machine(states=states, transitions=transitions, initial='A')
        m.walk()
        self.assertEqual(m.state, 'B')
        # Define with list of lists
        transitions = [
            ['walk', 'A', 'B'],
            ['run', 'B', 'C'],
            ['sprint', 'C', 'D']
        ]
        m = Machine(states=states, transitions=transitions, initial='A')
        m.to_C()
        m.sprint()
        self.assertEqual(m.state, 'D')

    def test_add_states(self):
        s = self.stuff
        s.machine.add_state('X')
        s.machine.add_state('Y')
        s.machine.add_state('Z')
        event = s.machine.events['to_{0}'.format(s.state)]
        self.assertEqual(1, len(event.transitions['X']))

    def test_transitioning(self):
        s = self.stuff
        s.machine.add_transition('advance', 'A', 'B')
        s.machine.add_transition('advance', 'B', 'C')
        s.machine.add_transition('advance', 'C', 'D')
        s.advance()
        self.assertEqual(s.state, 'B')
        self.assertFalse(s.is_A())
        self.assertTrue(s.is_B())
        s.advance()
        self.assertEqual(s.state, 'C')

    def test_pass_state_instances_instead_of_names(self):
        state_A = State('A')
        state_B = State('B')
        states = [state_A, state_B]
        m = Machine(states=states, initial=state_A)
        assert m.state == 'A'
        m.add_transition('advance', state_A, state_B)
        m.advance()
        assert m.state == 'B'
        state_B2 = State('B', on_enter='this_passes')
        with self.assertRaises(ValueError):
            m.add_transition('advance2', state_A, state_B2)
        m2 = Machine(states=states, initial=state_A.name)
        assert m.initial == m2.initial
        with self.assertRaises(ValueError):
            Machine(states=states, initial=State('A'))

    def test_conditions(self):
        s = self.stuff
        s.machine.add_transition('advance', 'A', 'B', conditions='this_passes')
        s.machine.add_transition('advance', 'B', 'C', unless=['this_fails'])
        s.machine.add_transition('advance', 'C', 'D', unless=['this_fails',
                                                              'this_passes'])
        s.advance()
        self.assertEqual(s.state, 'B')
        s.advance()
        self.assertEqual(s.state, 'C')
        s.advance()
        self.assertEqual(s.state, 'C')

    def test_uncallable_callbacks(self):
        s = self.stuff
        s.machine.add_transition('advance', 'A', 'B', conditions=['property_that_fails', 'is_false'])
        # make sure parameters passed by trigger events can be handled
        s.machine.add_transition('advance', 'A', 'C', before=['property_that_fails', 'is_false'])
        s.advance(level='MaximumSpeed')
        self.assertTrue(s.is_C())

    def test_conditions_with_partial(self):
        def check(result):
            return result

        s = self.stuff
        s.machine.add_transition('advance', 'A', 'B',
                                 conditions=partial(check, True))
        s.machine.add_transition('advance', 'B', 'C',
                                 unless=[partial(check, False)])
        s.machine.add_transition('advance', 'C', 'D',
                                 unless=[partial(check, False), partial(check, True)])
        s.advance()
        self.assertEqual(s.state, 'B')
        s.advance()
        self.assertEqual(s.state, 'C')
        s.advance()
        self.assertEqual(s.state, 'C')

    def test_multiple_add_transitions_from_state(self):
        s = self.stuff
        s.machine.add_transition(
            'advance', 'A', 'B', conditions=['this_fails'])
        s.machine.add_transition('advance', 'A', 'C')
        s.advance()
        self.assertEqual(s.state, 'C')

    def test_use_machine_as_model(self):
        states = ['A', 'B', 'C', 'D']
        m = Machine(states=states, initial='A')
        m.add_transition('move', 'A', 'B')
        m.add_transition('move_to_C', 'B', 'C')
        m.move()
        self.assertEqual(m.state, 'B')

    def test_state_change_listeners(self):
        s = self.stuff
        s.machine.add_transition('advance', 'A', 'B')
        s.machine.add_transition('reverse', 'B', 'A')
        s.machine.on_enter_B('hello_world')
        s.machine.on_exit_B('goodbye')
        s.advance()
        self.assertEqual(s.state, 'B')
        self.assertEqual(s.message, 'Hello World!')
        s.reverse()
        self.assertEqual(s.state, 'A')
        self.assertTrue(s.message is not None and s.message.startswith('So long'))

    def test_before_after_callback_addition(self):
        m = Machine(Stuff(), states=['A', 'B', 'C'], initial='A')
        m.add_transition('move', 'A', 'B')
        trans = m.events['move'].transitions['A'][0]
        trans.add_callback('after', 'increase_level')
        m.model.move()
        self.assertEqual(m.model.level, 2)

    def test_before_after_transition_listeners(self):
        m = Machine(Stuff(), states=['A', 'B', 'C'], initial='A')
        m.add_transition('move', 'A', 'B')
        m.add_transition('move', 'B', 'C')

        m.before_move('increase_level')
        m.model.move()
        self.assertEqual(m.model.level, 2)
        m.model.move()
        self.assertEqual(m.model.level, 3)

    def test_prepare(self):
        m = Machine(Stuff(), states=['A', 'B', 'C'], initial='A')
        m.add_transition('move', 'A', 'B', prepare='increase_level')
        m.add_transition('move', 'B', 'C', prepare='increase_level')
        m.add_transition('move', 'C', 'A', prepare='increase_level', conditions='this_fails')
        m.add_transition('dont_move', 'A', 'C', prepare='increase_level')

        m.prepare_move('increase_level')

        m.model.move()
        self.assertEqual(m.model.state, 'B')
        self.assertEqual(m.model.level, 3)

        m.model.move()
        self.assertEqual(m.model.state, 'C')
        self.assertEqual(m.model.level, 5)

        # State does not advance, but increase_level still runs
        m.model.move()
        self.assertEqual(m.model.state, 'C')
        self.assertEqual(m.model.level, 7)

        # An invalid transition shouldn't execute the callback
        try:
            m.model.dont_move()
        except MachineError as e:
            self.assertTrue("Can't trigger event" in str(e))

        self.assertEqual(m.model.state, 'C')
        self.assertEqual(m.model.level, 7)

    def test_state_model_change_listeners(self):
        s = self.stuff
        s.machine.add_transition('go_e', 'A', 'E')
        s.machine.add_transition('go_f', 'E', 'F')
        s.machine.on_enter_F('hello_F')
        s.go_e()
        self.assertEqual(s.state, 'E')
        self.assertEqual(s.message, 'I am E!')
        s.go_f()
        self.assertEqual(s.state, 'F')
        self.assertEqual(s.exit_message, 'E go home...')
        self.assertIn('I am F!', s.message or "")
        self.assertIn('Hello F!', s.message or "")

    def test_inheritance(self):
        states = ['A', 'B', 'C', 'D', 'E']
        s = InheritedStuff(states=states, initial='A')
        s.add_transition('advance', 'A', 'B', conditions='this_passes')
        s.add_transition('advance', 'B', 'C')
        s.add_transition('advance', 'C', 'D')
        s.advance()
        self.assertEqual(s.state, 'B')
        self.assertFalse(s.is_A())
        self.assertTrue(s.is_B())
        s.advance()
        self.assertEqual(s.state, 'C')

        class NewMachine(Machine):
            def __init__(self, *args, **kwargs):
                super(NewMachine, self).__init__(*args, **kwargs)

        n = NewMachine(states=states, transitions=[['advance', 'A', 'B']], initial='A')
        self.assertTrue(n.is_A())
        n.advance()
        self.assertTrue(n.is_B())
        with self.assertRaises(ValueError):
            NewMachine(state=['A', 'B'])

    def test_send_event_data_callbacks(self):
        states = ['A', 'B', 'C', 'D', 'E']
        s = Stuff()
        # First pass positional and keyword args directly to the callback
        m = Machine(model=s, states=states, initial='A', send_event=False,
                    auto_transitions=True)
        m.add_transition(
            trigger='advance', source='A', dest='B', before='set_message')
        s.advance(message='Hallo. My name is Inigo Montoya.')
        self.assertTrue(s.message is not None and s.message.startswith('Hallo.'))
        s.to_A()
        s.advance('Test as positional argument')
        self.assertTrue(s.message is not None and s.message.startswith('Test as'))
        # Now wrap arguments in an EventData instance
        m.send_event = True
        m.add_transition(
            trigger='advance', source='B', dest='C', before='extract_message')
        s.advance(message='You killed my father. Prepare to die.')
        self.assertTrue(s.message is not None and s.message.startswith('You'))

    def test_send_event_data_conditions(self):
        states = ['A', 'B', 'C', 'D']
        s = Stuff()
        # First pass positional and keyword args directly to the condition
        m = Machine(model=s, states=states, initial='A', send_event=False)
        m.add_transition(
            trigger='advance', source='A', dest='B',
            conditions='this_fails_by_default')
        s.advance(boolean=True)
        self.assertEqual(s.state, 'B')
        # Now wrap arguments in an EventData instance
        m.send_event = True
        m.add_transition(
            trigger='advance', source='B', dest='C',
            conditions='extract_boolean')
        s.advance(boolean=False)
        self.assertEqual(s.state, 'B')

    def test_auto_transitions(self):
        states = ['A', {'name': 'B'}, State(name='C')]  # type: Sequence[StateConfig]
        m = Machine(states=states, initial='A', auto_transitions=True)
        m.to_B()
        self.assertEqual(m.state, 'B')
        m.to_C()
        self.assertEqual(m.state, 'C')
        m.to_A()
        self.assertEqual(m.state, 'A')
        # Should fail if auto transitions is off...
        m = Machine(states=states, initial='A', auto_transitions=False)
        with self.assertRaises(AttributeError):
            m.to_C()

    def test_ordered_transitions(self):
        states = ['beginning', 'middle', 'end']
        m = Machine(states=states)
        m.add_ordered_transitions()
        self.assertEqual(m.state, 'initial')
        m.next_state()
        self.assertEqual(m.state, 'beginning')
        m.next_state()
        m.next_state()
        self.assertEqual(m.state, 'end')
        m.next_state()
        self.assertEqual(m.state, 'initial')

        # Include initial state in loop
        m = Machine(states=states)
        m.add_ordered_transitions(loop_includes_initial=False)
        m.to_end()
        m.next_state()
        self.assertEqual(m.state, 'beginning')

        # Do not loop transitions
        m = Machine(states=states)
        m.add_ordered_transitions(loop=False)
        m.to_end()
        with self.assertRaises(MachineError):
            m.next_state()

        # Test user-determined sequence and trigger name
        m = Machine(states=states, initial='beginning')
        m.add_ordered_transitions(['end', 'beginning'], trigger='advance')
        m.advance()
        self.assertEqual(m.state, 'end')
        m.advance()
        self.assertEqual(m.state, 'beginning')

        # Via init argument
        m = Machine(states=states, initial='beginning', ordered_transitions=True)
        m.next_state()
        self.assertEqual(m.state, 'middle')

        # Alter initial state
        m = Machine(states=states, initial='middle', ordered_transitions=True)
        m.next_state()
        self.assertEqual(m.state, 'end')
        m.next_state()
        self.assertEqual(m.state, 'beginning')

        # Partial state machine without the initial state
        m = Machine(states=states, initial='beginning')
        m.add_ordered_transitions(['middle', 'end'])
        self.assertEqual(m.state, 'beginning')
        with self.assertRaises(MachineError):
            m.next_state()
        m.to_middle()
        for s in ('end', 'middle', 'end'):
            m.next_state()
            self.assertEqual(m.state, s)

    def test_ordered_transition_error(self):
        m = Machine(states=['A'], initial='A')
        with self.assertRaises(ValueError):
            m.add_ordered_transitions()
        m.add_state('B')
        m.add_ordered_transitions()
        m.add_state('C')
        with self.assertRaises(ValueError):
            m.add_ordered_transitions(['C'])

    def test_ignore_invalid_triggers(self):
        a_state = State('A')
        transitions = [['a_to_b', 'A', 'B']]
        # Exception is triggered by default
        b_state = State('B')
        m1 = Machine(states=[a_state, b_state], transitions=transitions,
                     initial='B')
        with self.assertRaises(MachineError):
            m1.a_to_b()
        # Set default value on machine level
        m2 = Machine(states=[a_state, b_state], transitions=transitions,
                     initial='B', ignore_invalid_triggers=True)
        m2.a_to_b()
        # Exception is suppressed, so this passes
        b_state = State('B', ignore_invalid_triggers=True)
        m3 = Machine(states=[a_state, b_state], transitions=transitions,
                     initial='B')
        m3.a_to_b()
        # Set for some states but not others
        new_states = ['C', 'D']
        m1.add_states(new_states, ignore_invalid_triggers=True)
        m1.to_D()
        m1.a_to_b()  # passes because exception suppressed for D
        m1.to_B()
        with self.assertRaises(MachineError):
            m1.a_to_b()
        # State value overrides machine behaviour
        m3 = Machine(states=[a_state, b_state], transitions=transitions,
                     initial='B', ignore_invalid_triggers=False)
        m3.a_to_b()

    def test_string_callbacks(self):

        m = Machine(states=['A', 'B'],
                    before_state_change='before_state_change',
                    after_state_change='after_state_change', send_event=True,
                    initial='A', auto_transitions=True)

        m.before_state_change = MagicMock()
        m.after_state_change = MagicMock()

        m.to_B()

        self.assertTrue(m.before_state_change[0].called)
        self.assertTrue(m.after_state_change[0].called)

        # after_state_change should have been called with EventData
        event_data = m.after_state_change[0].call_args[0][0]
        self.assertIsInstance(event_data, EventData)
        self.assertTrue(event_data.result)

    def test_function_callbacks(self):
        before_state_change = MagicMock()
        after_state_change = MagicMock()

        m = Machine(states=['A', 'B'],
                    before_state_change=before_state_change,
                    after_state_change=after_state_change, send_event=True,
                    initial='A', auto_transitions=True)
        self.assertEqual(before_state_change, m.before_state_change[0])
        self.assertEqual(after_state_change, m.after_state_change[0])
        m.to_B()
        self.assertTrue(before_state_change.called)
        self.assertTrue(after_state_change.called)

    def test_state_callbacks(self):

        class Model:
            def on_enter_A(self):
                pass

            def on_exit_A(self):
                pass

            def on_enter_B(self):
                pass

            def on_exit_B(self):
                pass

        states = [State(name='A', on_enter='on_enter_A', on_exit='on_exit_A'),
                  State(name='B', on_enter='on_enter_B', on_exit='on_exit_B')]

        machine = Machine(Model(), states=states)
        state_a = machine.get_state('A')
        state_b = machine.get_state('B')
        self.assertEqual(len(state_a.on_enter), 1)
        self.assertEqual(len(state_a.on_exit), 1)
        self.assertEqual(len(state_b.on_enter), 1)
        self.assertEqual(len(state_b.on_exit), 1)

    def test_state_callable_callbacks(self):

        class Model:

            def __init__(self):
                self.exit_A_called = False
                self.exit_B_called = False

            def on_enter_A(self, event):
                pass

            def on_enter_B(self, event):
                pass

        states = [State(name='A', on_enter='on_enter_A', on_exit='tests.test_core.on_exit_A'),
                  State(name='B', on_enter='on_enter_B', on_exit=on_exit_B),
                  State(name='C', on_enter='tests.test_core.AAAA')]

        model = Model()
        machine = Machine(model, states=states, send_event=True, initial='A')
        state_a = machine.get_state('A')
        state_b = machine.get_state('B')
        self.assertEqual(len(state_a.on_enter), 1)
        self.assertEqual(len(state_a.on_exit), 1)
        self.assertEqual(len(state_b.on_enter), 1)
        self.assertEqual(len(state_b.on_exit), 1)
        model.to_B()
        self.assertTrue(model.exit_A_called)
        model.to_A()
        self.assertTrue(model.exit_B_called)
        with self.assertRaises(AttributeError):
            model.to_C()

    def test_pickle(self):
        import sys
        if sys.version_info < (3, 4):
            import dill as pickle
        else:
            import pickle

        states = ['A', 'B', 'C', 'D']
        # Define with list of dictionaries
        transitions = [
            {'trigger': 'walk', 'source': 'A', 'dest': 'B'},
            {'trigger': 'run', 'source': 'B', 'dest': 'C'},
            {'trigger': 'sprint', 'source': 'C', 'dest': 'D'}
        ]  # type: Sequence[TransitionConfigDict]
        m = Machine(states=states, transitions=transitions, initial='A')
        m.walk()
        dump = pickle.dumps(m)
        self.assertIsNotNone(dump)
        m2 = pickle.loads(dump)
        self.assertEqual(m.state, m2.state)
        m2.run()

    def test_pickle_model(self):
        import sys
        if sys.version_info < (3, 4):
            import dill as pickle
        else:
            import pickle

        self.stuff.to_B()
        dump = pickle.dumps(self.stuff)
        self.assertIsNotNone(dump)
        model2 = pickle.loads(dump)
        self.assertEqual(self.stuff.state, model2.state)
        model2.to_F()

    def test_queued(self):
        states = ['A', 'B', 'C', 'D']
        # Define with list of dictionaries

        def change_state(machine):
            self.assertEqual(machine.state, 'A')
            if machine.has_queue:
                machine.run(machine=machine)
                self.assertEqual(machine.state, 'A')
            else:
                with self.assertRaises(MachineError):
                    machine.run(machine=machine)

        transitions = [
            {'trigger': 'walk', 'source': 'A', 'dest': 'B', 'before': change_state},
            {'trigger': 'run', 'source': 'B', 'dest': 'C'},
            {'trigger': 'sprint', 'source': 'C', 'dest': 'D'}
        ]  # type: Sequence[TransitionConfig]

        m = Machine(states=states, transitions=transitions, initial='A')
        m.walk(machine=m)
        self.assertEqual(m.state, 'B')
        m = Machine(states=states, transitions=transitions, initial='A', queued=True)
        m.walk(machine=m)
        self.assertEqual(m.state, 'C')

    def test_queued_errors(self):
        def before_change(machine):
            if machine.has_queue:
                machine.to_A(machine)
            machine._queued = False

        def after_change(machine):
            machine.to_C(machine)

        states = ['A', 'B', 'C']
        transitions = [{
            'trigger': 'do', 'source': '*', 'dest': 'C',
            'before': partial(self.stuff.this_raises, ValueError)
        }]  # type: Sequence[TransitionConfig]

        m = Machine(states=states, transitions=transitions, queued=True,
                    before_state_change=before_change, after_state_change=after_change)
        with self.assertRaises(MachineError):
            m.to_B(machine=m)

        with self.assertRaises(ValueError):
            m.do(machine=m)

    def test_queued_remove(self):
        m = self.machine_cls(model=None, states=['A', 'B', 'C'], initial='A', queued=True)
        assert_equal = self.assertEqual

        class BaseModel:
            def on_enter_A(self):
                pass

            def on_enter_B(self):
                pass

            def on_enter_C(self):
                pass

        class SubModel(BaseModel):
            def __init__(self):
                self.inner = BaseModel()

            def on_enter_A(self):
                self.to_B()
                self.inner.to_B()

            def on_enter_B(self):
                self.to_C()
                self.inner.to_C()
                # queue should contain to_B(), inner.to_B(), to_C(), inner.to_C()
                assert_equal(4, len(m._transition_queue))
                m.remove_model(self)
                # since to_B() is currently executed it should still be in the list, to_C should be gone
                assert_equal(3, len(m._transition_queue))

            def on_enter_C(self):
                raise RuntimeError("Event was not cancelled")
        model = SubModel()
        m.add_model([model, model.inner])
        model.to_A()
        # test whether models can be removed outside event queue
        m.remove_model(model.inner)
        self.assertTrue(model.inner.is_C())

    def test___getattr___and_identify_callback(self):
        m = self.machine_cls(Stuff(), states=['A', 'B', 'C'], initial='A')
        m.add_transition('move', 'A', 'B')
        m.add_transition('move', 'B', 'C')

        callback = m.__getattr__('before_move')
        self.assertTrue(callable(callback))

        with self.assertRaises(AttributeError):
            m.__getattr__('before_no_such_transition')

        with self.assertRaises(AttributeError):
            m.__getattr__('before_no_such_transition')

        with self.assertRaises(AttributeError):
            m.__getattr__('__no_such_method__')

        with self.assertRaises(AttributeError):
            m.__getattr__('')

        type, target = m._identify_callback('on_exit_foobar')
        self.assertEqual(type, 'on_exit')
        self.assertEqual(target, 'foobar')

        type, target = m._identify_callback('on_exitfoobar')
        self.assertEqual(type, None)
        self.assertEqual(target, None)

        type, target = m._identify_callback('notacallback_foobar')
        self.assertEqual(type, None)
        self.assertEqual(target, None)

        type, target = m._identify_callback('totallyinvalid')
        self.assertEqual(type, None)
        self.assertEqual(target, None)

        type, target = m._identify_callback('before__foobar')
        self.assertEqual(type, 'before')
        self.assertEqual(target, '_foobar')

        type, target = m._identify_callback('before__this__user__likes__underscores___')
        self.assertEqual(type, 'before')
        self.assertEqual(target, '_this__user__likes__underscores___')

        type, target = m._identify_callback('before_stuff')
        self.assertEqual(type, 'before')
        self.assertEqual(target, 'stuff')

        type, target = m._identify_callback('before_trailing_underscore_')
        self.assertEqual(type, 'before')
        self.assertEqual(target, 'trailing_underscore_')

        type, target = m._identify_callback('before_')
        self.assertIs(type, None)
        self.assertIs(target, None)

        type, target = m._identify_callback('__')
        self.assertIs(type, None)
        self.assertIs(target, None)

        type, target = m._identify_callback('')
        self.assertIs(type, None)
        self.assertIs(target, None)

    def test_state_and_transition_with_underscore(self):
        m = Machine(Stuff(), states=['_A_', '_B_', '_C_'], initial='_A_')
        m.add_transition('_move_', '_A_', '_B_', prepare='increase_level')
        m.add_transition('_after_', '_B_', '_C_', prepare='increase_level')
        m.add_transition('_on_exit_', '_C_', '_A_', prepare='increase_level', conditions='this_fails')

        m.model._move_()
        self.assertEqual(m.model.state, '_B_')
        self.assertEqual(m.model.level, 2)

        m.model._after_()
        self.assertEqual(m.model.state, '_C_')
        self.assertEqual(m.model.level, 3)

        # State does not advance, but increase_level still runs
        m.model._on_exit_()
        self.assertEqual(m.model.state, '_C_')
        self.assertEqual(m.model.level, 4)

    def test_callback_identification(self):
        m = Machine(Stuff(), states=['A', 'B', 'C', 'D', 'E', 'F'], initial='A')
        m.add_transition('transition', 'A', 'B', before='increase_level')
        m.add_transition('after', 'B', 'C', before='increase_level')
        m.add_transition('on_exit_A', 'C', 'D', before='increase_level', conditions='this_fails')
        m.add_transition('check', 'C', 'E', before='increase_level')
        m.add_transition('prepare', 'E', 'F', before='increase_level')
        m.add_transition('before', 'F', 'A', before='increase_level')

        m.before_transition('increase_level')
        m.before_after('increase_level')
        m.before_on_exit_A('increase_level')
        m.after_check('increase_level')
        m.before_prepare('increase_level')
        m.before_before('increase_level')

        m.model.transition()
        self.assertEqual(m.model.state, 'B')
        self.assertEqual(m.model.level, 3)

        m.model.after()
        self.assertEqual(m.model.state, 'C')
        self.assertEqual(m.model.level, 5)

        m.model.on_exit_A()
        self.assertEqual(m.model.state, 'C')
        self.assertEqual(m.model.level, 5)

        m.model.check()
        self.assertEqual(m.model.state, 'E')
        self.assertEqual(m.model.level, 7)

        m.model.prepare()
        self.assertEqual(m.model.state, 'F')
        self.assertEqual(m.model.level, 9)

        m.model.before()
        self.assertEqual(m.model.state, 'A')
        self.assertEqual(m.model.level, 11)

        # An invalid transition shouldn't execute the callback
        with self.assertRaises(MachineError):
            m.model.on_exit_A()

    def test_process_trigger(self):
        m = Machine(states=['raw', 'processed'], initial='raw')
        m.add_transition('process', 'raw', 'processed')

        m.process()
        self.assertEqual(m.state, 'processed')

    def test_multiple_models(self):
        s1, s2 = Stuff(), Stuff()
        states = ['A', 'B', 'C']

        m = Machine(model=[s1, s2], states=states,
                    initial=states[0])
        self.assertEqual(len(m.models), 2)
        self.assertTrue(isinstance(m.model, list) and len(m.model) == 2)
        m.add_transition('advance', 'A', 'B')
        s1.advance()
        self.assertEqual(s1.state, 'B')
        self.assertEqual(s2.state, 'A')
        m = Machine(model=s1, states=states,
                    initial=states[0])
        # for backwards compatibility model should return a model instance
        # rather than a list
        self.assertNotIsInstance(m.model, list)

    def test_dispatch(self):
        s1, s2 = Stuff(), Stuff()
        states = ['A', 'B', 'C']
        m = Machine(model=s1, states=states, ignore_invalid_triggers=True,
                    initial=states[0], transitions=[['go', 'A', 'B'], ['go', 'B', 'C']])
        m.add_model(s2, initial='B')
        assert m.dispatch('go')
        self.assertEqual(s1.state, 'B')
        self.assertEqual(s2.state, 'C')

    def test_dispatch_with_error(self):
        s1, s2 = Stuff(), Stuff()
        states = ['A', 'B', 'C']
        m = Machine(model=s1, states=states, ignore_invalid_triggers=True,
                    initial=states[0], transitions=[['go', 'B', 'C']])
        m.add_model(s2, initial='B')
        assert not m.dispatch('go')
        self.assertEqual(s1.state, 'A')
        self.assertEqual(s2.state, 'C')

    def test_remove_model(self):
        m = self.machine_cls()
        self.assertIn(m, m.models)
        m.remove_model(m)
        self.assertNotIn(m, m.models)

    def test_string_trigger(self):
        def return_value(value):
            return value

        class Model:
            def trigger(self, value):
                return value

        self.stuff.machine.add_transition('do', '*', 'C')
        self.stuff.trigger('do')
        self.assertTrue(self.stuff.is_C())
        self.stuff.machine.add_transition('maybe', 'C', 'A', conditions=return_value)
        self.assertFalse(self.stuff.trigger('maybe', value=False))
        self.assertTrue(self.stuff.trigger('maybe', value=True))
        self.assertTrue(self.stuff.is_A())
        with self.assertRaises(AttributeError):
            self.stuff.trigger('not_available')
        with self.assertRaises(MachineError):
            self.stuff.trigger('maybe')

        model = Model()
        m = Machine(model=model)
        self.assertEqual(model.trigger(5), 5)
        self.stuff.machine.add_transition('do_raise_keyerror', '*', 'C',
                                          before=partial(self.stuff.this_raises, KeyError))
        with self.assertRaises(KeyError):
            self.stuff.trigger('do_raise_keyerror')

        self.stuff.machine.get_model_state(self.stuff).ignore_invalid_triggers = True
        self.stuff.trigger('should_not_raise_anything')
        self.stuff.trigger('to_A')
        self.assertTrue(self.stuff.is_A())
        self.stuff.machine.ignore_invalid_triggers = True
        self.stuff.trigger('should_not_raise_anything')

    def test_get_triggers(self):
        states = ['A', 'B', 'C']
        transitions = [['a2b', 'A', 'B'],
                       ['a2c', 'A', 'C'],
                       ['c2b', 'C', 'B']]
        machine = Machine(states=states, transitions=transitions, initial='A', auto_transitions=False)
        self.assertEqual(len(machine.get_triggers('A')), 2)
        self.assertEqual(len(machine.get_triggers('B')), 0)
        self.assertEqual(len(machine.get_triggers('C')), 1)
        # self stuff machine should have to-transitions to every state
        m = self.stuff.machine
        self.assertEqual(len(m.get_triggers('B')), len(m.states))
        trigger_name = m.get_triggers('B')
        trigger_state = m.get_triggers(m.states['B'])
        self.assertEqual(trigger_name, trigger_state)

    def test_skip_override(self):
        local_mock = MagicMock()

        class Model(object):

            def go(self):
                local_mock()
        model = Model()
        transitions = [['go', 'A', 'B'], ['advance', 'A', 'B']]
        m = self.stuff.machine_cls(model=model, states=['A', 'B'], transitions=transitions, initial='A')
        model.go()
        self.assertEqual(model.state, 'A')
        self.assertTrue(local_mock.called)
        model.advance()
        self.assertEqual(model.state, 'B')
        model.to_A()
        model.trigger('go')
        self.assertEqual(model.state, 'B')

    @skipIf(sys.version_info < (3, ),
            "String-checking disabled on PY-2 because is different")
    def test_repr(self):
        def a_condition(event_data):
            self.assertRegex(
                str(event_data.transition.conditions),
                r"\[<Condition\(<function TestTransitions.test_repr.<locals>"
                r".a_condition at [^>]+>\)@\d+>\]")
            return True

        # No transition has been assigned to EventData yet
        def check_prepare_repr(event_data):
            self.assertRegex(
                str(event_data),
                r"<EventData\(<Event\('do_strcheck'\)@\d+>, "
                r"<State\('A'\)@\d+>, "
                r"None\)@\d+>")

        def check_before_repr(event_data):
            self.assertRegex(
                str(event_data),
                r"<EventData\(<Event\('do_strcheck'\)@\d+>, "
                r"<State\('A'\)@\d+>, "
                r"<Transition\('A', 'B'\)@\d+>\)@\d+>")
            m.checked = True

        m = Machine(states=['A', 'B'],
                    prepare_event=check_prepare_repr,
                    before_state_change=check_before_repr, send_event=True,
                    initial='A')
        m.add_transition('do_strcheck', 'A', 'B', conditions=a_condition)

        self.assertTrue(m.do_strcheck())
        self.assertIn('checked', vars(m))

    def test_machine_prepare(self):

        global_mock = MagicMock()
        local_mock = MagicMock()

        def global_callback():
            global_mock()

        def local_callback():
            local_mock()

        def always_fails():
            return False

        transitions = [
            {'trigger': 'go', 'source': 'A', 'dest': 'B', 'conditions': always_fails, 'prepare': local_callback},
            {'trigger': 'go', 'source': 'A', 'dest': 'B', 'conditions': always_fails, 'prepare': local_callback},
            {'trigger': 'go', 'source': 'A', 'dest': 'B', 'conditions': always_fails, 'prepare': local_callback},
            {'trigger': 'go', 'source': 'A', 'dest': 'B', 'conditions': always_fails, 'prepare': local_callback},
            {'trigger': 'go', 'source': 'A', 'dest': 'B', 'prepare': local_callback},

        ]  # type: Sequence[TransitionConfig]
        m = Machine(states=['A', 'B'], transitions=transitions,
                    prepare_event=global_callback, initial='A')

        m.go()
        self.assertEqual(global_mock.call_count, 1)
        self.assertEqual(local_mock.call_count, len(transitions))

    def test_machine_finalize(self):

        finalize_mock = MagicMock()

        def always_fails(event_data):
            return False

        transitions = [
            {'trigger': 'go', 'source': 'A', 'dest': 'B'},
            {'trigger': 'planA', 'source': 'B', 'dest': 'A', 'conditions': always_fails},
            {'trigger': 'planB', 'source': 'B', 'dest': 'A',
             'conditions': partial(self.stuff.this_raises, RuntimeError)}
        ]
        m = self.stuff.machine_cls(states=['A', 'B'], transitions=transitions,
                                   finalize_event=finalize_mock, initial='A', send_event=True)

        m.go()
        self.assertEqual(finalize_mock.call_count, 1)
        m.planA()

        event_data = finalize_mock.call_args[0][0]
        self.assertIsInstance(event_data, EventData)
        self.assertEqual(finalize_mock.call_count, 2)
        self.assertFalse(event_data.result)
        with self.assertRaises(RuntimeError):
            m.planB()

        m.finalize_event.append(partial(self.stuff.this_raises, ValueError))
        # ValueError in finalize should be suppressed
        # but mock should have been called anyway
        with self.assertRaises(RuntimeError):
            m.planB()
        self.assertEqual(4, finalize_mock.call_count)

    def test_machine_finalize_exception(self):

        def finalize_callback(event):
            self.assertIsInstance(event.error, ZeroDivisionError)

        m = self.stuff.machine_cls(states=['A', 'B'], send_event=True, initial='A',
                                   before_state_change=partial(self.stuff.this_raises, ZeroDivisionError),
                                   finalize_event=finalize_callback)

        with self.assertRaises(ZeroDivisionError):
            m.to_B()

    def test_prep_ordered_arg(self):
        self.assertTrue(len(_prep_ordered_arg(3, None)) == 3)
        self.assertTrue(all(a is None for a in _prep_ordered_arg(3, None)))
        with self.assertRaises(ValueError):
            # deliberately passing wrong arguments
            _prep_ordered_arg(3, [None, None])  # type: ignore

    def test_ordered_transition_callback(self):
        class Model:
            def __init__(self):
                self.flag = False

            def make_true(self):
                self.flag = True

        model = Model()
        states = ['beginning', 'middle', 'end']
        transits = [None, None, 'make_true']
        m = Machine(model, states, initial='beginning')
        m.add_ordered_transitions(before=transits)
        model.next_state()
        self.assertFalse(model.flag)
        model.next_state()
        model.next_state()
        self.assertTrue(model.flag)

    def test_ordered_transition_condition(self):
        class Model:
            def __init__(self):
                self.blocker = False

            def check_blocker(self):
                return self.blocker

        model = Model()
        states = ['beginning', 'middle', 'end']
        m = Machine(model, states, initial='beginning')
        m.add_ordered_transitions(conditions=[None, None, 'check_blocker'])
        model.to_end()
        self.assertFalse(model.next_state())
        model.blocker = True
        self.assertTrue(model.next_state())

    def test_get_transitions(self):
        states = ['A', 'B', 'C', 'D']
        m = self.machine_cls(states=states, initial='A', auto_transitions=False)
        m.add_transition('go', ['A', 'B', 'C'], 'D')
        m.add_transition('run', 'A', 'D')
        self.assertEqual(
            {(t.source, t.dest) for t in m.get_transitions('go')},
            {('A', 'D'), ('B', 'D'), ('C', 'D')})
        self.assertEqual(
            [(t.source, t.dest)
             for t in m.get_transitions(source='A', dest='D')],
            [('A', 'D'), ('A', 'D')])
        self.assertEqual(
            sorted([(t.source, t.dest)
                    for t in m.get_transitions(dest='D')]),
            [('A', 'D'), ('A', 'D'), ('B', 'D'), ('C', 'D')])
        self.assertEqual(
            [(t.source, t.dest)
             for t in m.get_transitions(source=m.states['A'], dest=m.states['D'])],
            [('A', 'D'), ('A', 'D')])
        self.assertEqual(
            sorted([(t.source, t.dest)
                    for t in m.get_transitions(dest=m.states['D'])]),
            [('A', 'D'), ('A', 'D'), ('B', 'D'), ('C', 'D')])

    def test_remove_transition(self):
        self.stuff.machine.add_transition('go', ['A', 'B', 'C'], 'D')
        self.stuff.machine.add_transition('walk', 'A', 'B')
        self.stuff.go()
        self.assertEqual(self.stuff.state, 'D')
        self.stuff.to_A()
        self.stuff.machine.remove_transition('go', source='A')
        with self.assertRaises(MachineError):
            self.stuff.go()
        self.stuff.machine.add_transition('go', 'A', 'D')
        self.stuff.walk()
        self.stuff.go()
        self.assertEqual(self.stuff.state, 'D')
        self.stuff.to_C()
        self.stuff.machine.remove_transition('go', dest='D')
        self.assertFalse(hasattr(self.stuff, 'go'))

    def test_remove_transition_state(self):
        self.stuff.machine.add_transition('go', ['A', 'B', 'C'], 'D')
        self.stuff.machine.add_transition('walk', 'A', 'B')
        self.stuff.go()
        self.assertEqual(self.stuff.state, 'D')
        self.stuff.to_A()
        self.stuff.machine.remove_transition('go', source=self.stuff.machine.states['A'])
        with self.assertRaises(MachineError):
            self.stuff.go()
        self.stuff.machine.add_transition('go', 'A', 'D')
        self.stuff.walk()
        self.stuff.go()
        self.assertEqual(self.stuff.state, 'D')
        self.stuff.to_C()
        self.stuff.machine.remove_transition('go', dest=self.stuff.machine.states['D'])
        self.assertFalse(hasattr(self.stuff, 'go'))

    def test_reflexive_transition(self):
        self.stuff.machine.add_transition('reflex', ['A', 'B'], '=', after='increase_level')
        self.assertEqual(self.stuff.state, 'A')
        self.stuff.reflex()
        self.assertEqual(self.stuff.state, 'A')
        self.assertEqual(self.stuff.level, 2)
        self.stuff.to_B()
        self.assertEqual(self.stuff.state, 'B')
        self.stuff.reflex()
        self.assertEqual(self.stuff.state, 'B')
        self.assertEqual(self.stuff.level, 3)
        self.stuff.to_C()
        with self.assertRaises(MachineError):
            self.stuff.reflex()
        self.assertEqual(self.stuff.level, 3)

    def test_internal_transition(self):
        m = Machine(Stuff(), states=['A', 'B'], initial='A')
        m.add_transition('move', 'A', None, prepare='increase_level')
        m.model.move()
        self.assertEqual(m.model.state, 'A')
        self.assertEqual(m.model.level, 2)

    def test_dynamic_model_state_attribute(self):
        class Model:
            def __init__(self):
                self.status = None
                self.state = 'some_value'

        m = self.machine_cls(Model(), states=['A', 'B'], initial='A', model_attribute='status')
        self.assertEqual(m.model.status, 'A')
        self.assertEqual(m.model.state, 'some_value')

        m.add_transition('move', 'A', 'B')
        m.model.move()

        self.assertEqual(m.model.status, 'B')
        self.assertEqual(m.model.state, 'some_value')

    def test_multiple_machines_per_model(self):
        class Model:
            def __init__(self):
                self.car_state = None
                self.driver_state = None

        instance = Model()
        machine_a = Machine(instance, states=['A', 'B'], initial='A', model_attribute='car_state')
        machine_a.add_transition('accelerate_car', 'A', 'B')
        machine_b = Machine(instance, states=['A', 'B'], initial='B', model_attribute='driver_state')
        machine_b.add_transition('driving', 'B', 'A')

        assert instance.car_state == 'A'
        assert instance.driver_state == 'B'
        assert instance.is_car_state_A()
        assert instance.is_driver_state_B()

        instance.accelerate_car()
        assert instance.car_state == 'B'
        assert instance.driver_state == 'B'
        assert not instance.is_car_state_A()
        assert instance.is_car_state_B()

        instance.driving()
        assert instance.driver_state == 'A'
        assert instance.car_state == 'B'
        assert instance.is_driver_state_A()
        assert not instance.is_driver_state_B()
        assert instance.to_driver_state_B()
        assert instance.driver_state == 'B'

    def test_initial_not_registered(self):
        m1 = self.machine_cls(states=['A', 'B'], initial=self.machine_cls.state_cls('C'))
        self.assertTrue(m1.is_C())
        self.assertTrue('C' in m1.states)

    def test_trigger_name_cannot_be_equal_to_model_attribute(self):
        m = self.machine_cls(states=['A', 'B'])

        with self.assertRaises(ValueError):
            m.add_transition(m.model_attribute, "A", "B")

    def test_new_state_in_enter_callback(self):

        machine = self.machine_cls(states=['A', 'B'], initial='A')

        def on_enter_B():
            state = self.machine_cls.state_cls(name='C')
            machine.add_state(state)
            machine.to_C()

        machine.on_enter_B(on_enter_B)
        machine.to_B()

    def test_on_exception_callback(self):
        mock = MagicMock()

        def on_exception(event_data):
            self.assertIsInstance(event_data.error, (ValueError, MachineError))
            mock()

        m = self.machine_cls(states=['A', 'B'], initial='A', transitions=[['go', 'A', 'B']], send_event=True,
                             after_state_change=partial(self.stuff.this_raises, ValueError))
        with self.assertRaises(ValueError):
            m.to_B()
        self.assertTrue(m.is_B())
        with self.assertRaises(MachineError):
            m.go()

        m.on_exception.append(on_exception)
        m.to_B()
        m.go()
        self.assertTrue(mock.called)
        self.assertEqual(2, mock.call_count)

    def test_may_transition(self):
        states = ['A', 'B', 'C']
        d = DummyModel()
        m = Machine(model=d, states=states, initial='A', auto_transitions=False)
        m.add_transition('walk', 'A', 'B')
        m.add_transition('stop', 'B', 'C')
        m.add_transition('wait', 'B', None)
        assert d.may_walk()
        assert d.may_trigger("walk")
        assert not d.may_stop()
        assert not d.may_trigger("stop")
        assert not d.may_wait()
        assert not d.may_trigger("wait")

        d.walk()
        assert not d.may_walk()
        assert not d.may_trigger("walk")
        assert d.may_stop()
        assert d.may_trigger("stop")
        assert d.may_wait()
        assert d.may_trigger("wait")

    def test_may_transition_for_autogenerated_triggers(self):
        states = ['A', 'B', 'C']
        m = Machine(states=states, initial='A')
        assert m.may_to_A()
        assert m.may_trigger("to_A")
        m.to_A()
        assert m.to_B()
        assert m.may_trigger("to_B")
        m.to_B()
        assert m.may_to_C()
        assert m.may_trigger("to_C")
        m.to_C()

    def test_may_transition_with_conditions(self):
        states = ['A', 'B', 'C']
        d = DummyModel()
        m = Machine(model=d, states=states, initial='A', auto_transitions=False)
        m.add_transition('walk', 'A', 'B', conditions=[lambda: False])
        m.add_transition('stop', 'B', 'C')
        m.add_transition('run', 'A', 'C')
        assert not d.may_walk()
        assert not d.may_trigger("walk")
        assert not d.may_stop()
        assert not d.may_trigger("stop")
        assert d.may_run()
        assert d.may_trigger("run")
        d.run()
        assert not d.may_run()
        assert not d.may_trigger("run")

    def test_machine_may_transitions(self):
        states = ['A', 'B', 'C']
        m = self.machine_cls(states=states, initial='A', auto_transitions=False)
        m.add_transition('walk', 'A', 'B', conditions=[lambda: False])
        m.add_transition('stop', 'B', 'C')
        m.add_transition('run', 'A', 'C')
        m.add_transition('reset', 'C', 'A')

        assert not m.may_walk()
        assert not m.may_trigger("walk")
        assert not m.may_stop()
        assert not m.may_trigger("stop")
        assert m.may_run()
        assert m.may_trigger("run")
        m.run()
        assert not m.may_run()
        assert not m.may_trigger("run")
        assert not m.may_stop()
        assert not m.may_trigger("stop")
        assert not m.may_walk()
        assert not m.may_trigger("walk")

    def test_may_transition_with_invalid_state(self):
        states = ['A', 'B', 'C']
        d = DummyModel()
        m = self.machine_cls(model=d, states=states, initial='A', auto_transitions=False)
        m.add_transition('walk', 'A', 'UNKNOWN')
        assert not d.may_walk()
        assert not d.may_trigger("walk")

    def test_may_transition_with_exception(self):
        stuff = Stuff(machine_cls=self.machine_cls, extra_kwargs={"send_event": True})
        stuff.machine.add_transition(trigger="raises", source="A", dest="B", prepare=partial(stuff.this_raises, RuntimeError("Prepare Exception")))
        stuff.machine.add_transition(trigger="raises", source="B", dest="C", conditions=partial(stuff.this_raises, ValueError("Condition Exception")))
        stuff.machine.add_transition(trigger="works", source="A", dest="B")

        def process_exception(event_data):
            assert event_data.error is not None
            assert event_data.transition is not None
            assert event_data.event.name == "raises"
            assert event_data.machine == stuff.machine

        with self.assertRaises(RuntimeError):
            stuff.may_raises()
        assert stuff.is_A()
        assert stuff.may_works()
        assert stuff.works()
        with self.assertRaises(ValueError):
            stuff.may_raises()
        with self.assertRaises(ValueError):
            stuff.may_trigger("raises")
        assert stuff.is_B()
        stuff.machine.on_exception.append(process_exception)
        assert not stuff.may_raises()
        assert not stuff.may_trigger("raises")
        assert stuff.to_A()
        assert not stuff.may_raises()
        assert not stuff.may_trigger("raises")

    def test_on_final(self):
        final_mock = MagicMock()
        machine = self.machine_cls(states=['A', {'name': 'B', 'final': True}], on_final=final_mock, initial='A')
        self.assertFalse(final_mock.called)
        machine.to_B()
        self.assertTrue(final_mock.called)
        machine.to_A()
        self.assertEqual(1, final_mock.call_count)
        machine.to_B()
        self.assertEqual(2, final_mock.call_count)

    def test_custom_transition(self):

        class MyTransition(self.machine_cls.transition_cls):  # type: ignore

            def __init__(self, source, dest, conditions=None, unless=None, before=None,
                         after=None, prepare=None, my_int=None, my_none=None, my_str=None, my_dict=None):
                super(MyTransition, self).__init__(source, dest, conditions, unless, before, after, prepare)
                self.my_int = my_int
                self.my_none = my_none
                self.my_str = my_str
                self.my_dict = my_dict

        class MyMachine(self.machine_cls):  # type: ignore
            transition_cls = MyTransition

        a_transition = {
            "trigger": "go", "source": "B", "dest": "A",
            "my_int": 42, "my_str": "foo", "my_dict": {"bar": "baz"}
        }
        transitions = [
            ["go", "A", "B"],
            a_transition
        ]

        m = MyMachine(states=["A", "B"], transitions=transitions, initial="A")
        m.add_transition("reset", "*", "A",
                         my_int=23, my_str="foo2", my_none=None, my_dict={"baz": "bar"})
        assert m.go()
        trans = m.get_transitions("go", "B")  # type: List[MyTransition]
        assert len(trans) == 1
        assert trans[0].my_str == a_transition["my_str"]
        assert trans[0].my_int == a_transition["my_int"]
        assert trans[0].my_dict == a_transition["my_dict"]
        assert trans[0].my_none is None
        trans = m.get_transitions("reset", "A")
        assert len(trans) == 1
        assert trans[0].my_str == "foo2"
        assert trans[0].my_int == 23
        assert trans[0].my_dict == {"baz": "bar"}
        assert trans[0].my_none is None
