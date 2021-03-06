# Copyright CEA (2011)
# Contributor: TATIBOUET Jeremie <tatibouetj@ocre.cea.fr>

"""
This modules defines the tests cases targeting the class
entity manager
"""

# Classes
from unittest import TestCase
from MilkCheck.EntityManager import entity_manager_self, EntityManager
from MilkCheck.Engine.BaseEntity import BaseEntity

class EntityManagerTest(TestCase):
    """Test cases for EntityManager"""

    def test_instanciation(self):
        """test on the instanciation of a manager"""
        manager = entity_manager_self()
        manager.entities['foo'] = BaseEntity('foo')
        same_manager = entity_manager_self()
        self.assertTrue(manager is same_manager)
        self.assertEqual(len(same_manager.entities), 1)

    def test_reverse_mod(self):
        """Test enable reverse mod over a bunch of entity"""
        ent1 = BaseEntity('foo')
        ent2 = BaseEntity('bar')
        manager = entity_manager_self()
        manager.entities['foo'] = ent1
        manager.entities['bar'] = ent2
        self.assertRaises(AssertionError, manager._reverse_mod, None)
        manager._reverse_mod(True)
        self.assertTrue(ent1._algo_reversed and ent2._algo_reversed)
        self.assertFalse(not ent1._algo_reversed and not ent2._algo_reversed)

    def test_iter_entities(self):
        """Test EntityManager iterator"""
        entity_manager_self().entities["foo"] = 1
        entity_manager_self().entities["bar"] = 3
        self.assertEqual(sorted(list(entity_manager_self().iter_entities())),
                                                                       [1, 3],
                                    "Inserted entities are not what expected")

    def tearDown(self):
        EntityManager._instance = None
