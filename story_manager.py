"""
Story Management Module
Extracted from app.py - handles story generation, summarization, and AI interactions
"""

import logging
import re
from typing import Dict, List, Any, Optional
from flask import session
from config import AI_CONFIG, SESSION_CONFIG
from game_logic import get_session_id


class StoryManager:
    """Manages story generation, summarization, and AI interactions."""
    
    def __init__(self, ai_client=None):
        self.client = ai_client
        self.config = AI_CONFIG
        
    def create_story_summary(self, full_story: str, mission: dict, player: dict) -> str:
        """Create an intelligent summary that preserves key plot points."""
        if len(full_story) < SESSION_CONFIG["story_summary_threshold"]:
            return full_story
        
        # Store full story in database before compression
        session_id = get_session_id()
        turn_count = session.get("turn_count", 0)
        
        # For now, store in session until database is ready
        story_backup_key = f"full_story_turn_{turn_count}"
        session[story_backup_key] = full_story
        
        # Extract key elements to preserve
        key_phrases = self._extract_key_phrases(mission, player)
        
        # Use AI to create intelligent summary if available
        if self.client:
            ai_summary = self._generate_ai_summary(full_story, key_phrases, mission)
            if ai_summary and len(ai_summary) < len(full_story) * 0.7:
                return ai_summary
        
        # Fallback to rule-based summary
        return self._create_rule_based_summary(full_story, key_phrases)
    
    def _extract_key_phrases(self, mission: dict, player: dict) -> List[str]:
        """Extract key phrases based on mission and player context."""
        key_phrases = []
        mission_name = mission.get("name", "").lower()
        
        # Mission-specific key elements
        if "sabotage" in mission_name:
            key_phrases.extend(["bridge", "explosives", "charges", "demolition", "target"])
        elif "rescue" in mission_name:
            key_phrases.extend(["prisoners", "pows", "rescue", "extraction", "captives"])
        elif "intel" in mission_name:
            key_phrases.extend(["documents", "intelligence", "classified", "information", "files"])
        
        # Character and tactical elements
        key_phrases.extend([
            player.get("name", "").lower(),
            player.get("class", "").lower(),
            "squad", "enemy", "objective", "mission"
        ])
        
        return [phrase for phrase in key_phrases if phrase]
    
    def _generate_ai_summary(self, full_story: str, key_phrases: List[str], mission: dict) -> Optional[str]:
        """Generate AI-powered story summary."""
        try:
            summary_prompt = (
                f"Compress this WWII mission story to under 400 words while preserving key plot points, "
                f"character decisions, mission objectives, and current tactical situation. "
                f"Key elements to preserve: {', '.join(key_phrases)}. "
                f"Story: {full_story}"
            )
            
            # Use AI chat function (assuming it exists in the main app)
            return self._ai_chat(
                "You are an expert story editor. Create concise but complete summaries.",
                summary_prompt,
                **self.config["story_summary"]
            )
        except Exception as e:
            logging.warning(f"AI summary failed: {e}")
            return None
    
    def _create_rule_based_summary(self, full_story: str, key_phrases: List[str]) -> str:
        """Create summary using rule-based approach."""
        sentences = full_story.split('. ')
        scored_sentences = []
        
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            # Score based on key phrases
            for phrase in key_phrases:
                if phrase and phrase in sentence_lower:
                    score += 1
            
            # Boost sentences with tactical/action content
            if any(word in sentence_lower for word in ["attack", "advance", "enemy", "fire", "combat"]):
                score += 1
            
            # Boost recent choices (sentences containing "chose" or numbers)
            if "chose" in sentence_lower or any(str(i) in sentence for i in range(1, 4)):
                score += 2
            
            scored_sentences.append((score, sentence))
        
        # Keep highest scoring sentences plus ensure narrative flow
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Build summary with key narrative elements
        summary_sentences = []
        
        # Always keep first 2 sentences (mission setup)
        if len(sentences) > 2:
            summary_sentences.extend(sentences[:2])
        
        # Add highest scoring middle content
        middle_sentences = [s[1] for s in scored_sentences if s[0] > 0][:3]
        summary_sentences.extend(middle_sentences)
        
        # Always keep last 3 sentences (current situation)
        if len(sentences) > 3:
            summary_sentences.extend(sentences[-3:])
        
        # Remove duplicates while preserving order
        seen = set()
        final_sentences = []
        for sentence in summary_sentences:
            if sentence not in seen:
                seen.add(sentence)
                final_sentences.append(sentence)
        
        summary = '. '.join(final_sentences)
        
        # Add bridging text to maintain flow if needed
        if len(final_sentences) > 1:
            summary = self._add_narrative_bridges(summary)
        
        return summary
    
    def _add_narrative_bridges(self, summary: str) -> str:
        """Add brief bridging text to improve story flow."""
        # Simple approach - add transition phrases at key points
        summary = summary.replace(". You chose", ". After careful consideration, you chose")
        summary = summary.replace(". The enemy", ". Meanwhile, the enemy")
        summary = summary.replace(". Your squad", ". Your squad then")
        
        return summary
    
    def _ai_chat(self, system_message: str, user_message: str, **kwargs) -> Optional[str]:
        """Placeholder for AI chat functionality - should be connected to main app's AI client."""
        # This will be connected to the main AI client in app.py
        if not self.client:
            return None
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"AI chat error: {e}")
            return None
    
    def generate_story_continuation(self, mission: Dict[str, Any], player: Dict[str, Any], 
                                  current_story: str, choice: str) -> str:
        """Generate story continuation based on player choice."""
        if not self.client:
            return self._get_fallback_story_continuation(choice)
        
        try:
            from config import get_ai_prompt_templates
            templates = get_ai_prompt_templates()
            
            prompt = templates["story_generation"].format(
                mission_name=mission.get("name", "Unknown Mission"),
                location=mission.get("location", "Unknown Location"),
                date=mission.get("date", "1944"),
                player_name=player.get("name", "Soldier"),
                rank=player.get("rank", "Private"),
                player_class=player.get("class", "Rifleman"),
                current_story=current_story[-500:],  # Last 500 chars for context
                choice=choice
            )
            
            return self._ai_chat(
                "You are a WWII military storyteller focused on historical accuracy and tactical realism.",
                prompt,
                **self.config["story_generation"]
            ) or self._get_fallback_story_continuation(choice)
            
        except Exception as e:
            logging.warning(f"Story generation failed: {e}")
            return self._get_fallback_story_continuation(choice)
    
    def _get_fallback_story_continuation(self, choice: str) -> str:
        """Get fallback story continuation when AI is unavailable."""
        fallback_stories = {
            "1": "You advance cautiously, weapon ready. The path ahead is fraught with danger, but your training guides you forward.",
            "2": "You take cover and assess the situation. Patience and tactical thinking will serve you better than rash action.",
            "3": "You coordinate with your squad, utilizing teamwork and combined tactics to overcome the challenge ahead."
        }
        
        return fallback_stories.get(choice.strip(), 
            "You proceed with determination, drawing upon your military training and experience to navigate the challenges ahead.")


# Global story manager instance (will be initialized with AI client in app.py)  
story_manager = StoryManager()