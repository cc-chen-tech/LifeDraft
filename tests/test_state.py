"""Tests for state management."""
import pytest
from src.game.state import PlayerState
from config.settings import settings


class TestPlayerState:
    """Test PlayerState class."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = PlayerState()
        assert state.energy == settings.INITIAL_ENERGY
        assert state.mood == settings.INITIAL_MOOD
        assert state.knowledge == settings.INITIAL_KNOWLEDGE
        assert state.wealth == settings.INITIAL_WEALTH
        assert state.age == settings.STARTING_AGE
        assert state.week == 0
        assert state.current_round == 0
        assert state.rounds_per_week == 3
    
    def test_update_energy(self):
        """Test updating energy."""
        state = PlayerState()
        state.update(energy=10)
        assert state.energy == settings.INITIAL_ENERGY + 10
        
        # Test bounds
        state.update(energy=200)
        assert state.energy == settings.MAX_RESOURCE
        
        state.update(energy=-200)
        assert state.energy == settings.MIN_RESOURCE
    
    def test_update_relationships(self):
        """Test updating relationships."""
        state = PlayerState()
        state.update(relationships={"Friend": 10})
        assert state.relationships["Friend"] == 60  # Default 50 + 10
        
        state.update(relationships={"Friend": -100})
        assert state.relationships["Friend"] == settings.MIN_RESOURCE
    
    def test_advance_week(self):
        """Test advancing to next week."""
        state = PlayerState()
        initial_week = state.week
        
        state.advance_week()
        assert state.week == initial_week + 1
        assert state.current_round == 0  # Round resets on new week
    
    def test_to_dict_from_dict(self):
        """Test serialization."""
        state = PlayerState()
        state.relationships = {"Test": 75}
        
        state_dict = state.to_dict()
        assert isinstance(state_dict, dict)
        assert "energy" in state_dict
        assert "relationships" in state_dict
        
        new_state = PlayerState.from_dict(state_dict)
        assert new_state.energy == state.energy
        assert new_state.relationships == state.relationships
    
    def test_validate(self):
        """Test state validation."""
        state = PlayerState()
        assert state.validate() is True
        
        # Test invalid state
        state.energy = 150
        with pytest.raises(ValueError):
            state.validate()
    
    def test_is_game_over(self):
        """Test game over condition."""
        state = PlayerState()
        assert state.is_game_over() is False
        
        # Game ends after TOTAL_WEEKS
        state.week = settings.TOTAL_WEEKS
        assert state.is_game_over() is True
    
    def test_get_current_phase(self):
        """Test phase detection."""
        state = PlayerState()
        assert state.get_current_phase() == "early_career"
        
        state.week = 25
        assert state.get_current_phase() == "establishing"
        
        state.week = 50
        assert state.get_current_phase() == "growth"
        
        state.week = 75
        assert state.get_current_phase() == "consolidation"
