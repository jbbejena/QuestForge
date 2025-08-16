// WWII Text Adventure - Mobile-Optimized JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize game features
    initializeTouchHandlers();
    initializeNotifications();
    initializeAutoSave();
    initializeMobileOptimizations();
    initializeProgressiveStory();
    initializeLoadingStates();
    initializeGameActions();
});

// Progressive story display system
function initializeProgressiveStory() {
    const newContent = document.getElementById('new-content');
    const baseStory = document.getElementById('base-story');
    
    if (newContent && baseStory) {
        // Show base story immediately
        baseStory.style.display = 'block';
        
        // Type out new content progressively
        typeWriterEffect(newContent, function() {
            // Auto-scroll to new content after typing
            newContent.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    } else {
        // Fallback to regular typewriter for full story
        const fullStory = document.getElementById('full-story');
        if (fullStory) {
            typeWriterEffect(fullStory);
        }
    }
}

// Enhanced typewriter effect with auto-scroll
function typeWriterEffect(element, callback) {
    if (!element) return;
    
    const originalHTML = element.innerHTML;
    const textContent = element.textContent || element.innerText;
    
    // Clear the element and show it
    element.innerHTML = '';
    element.style.display = 'block';
    
    let i = 0;
    const speed = 15; // Slightly faster for better UX
    let lastScrollTime = 0;
    
    function typeCharacter() {
        if (i < textContent.length) {
            // Handle line breaks
            if (textContent.substring(i, i + 1) === '\n') {
                element.innerHTML += '<br>';
            } else {
                element.innerHTML += textContent.charAt(i);
            }
            
            // Enhanced auto-scroll every few characters to keep text visible
            const now = Date.now();
            if (now - lastScrollTime > 50) { // Even more frequent scrolling for smoother experience
                // Always scroll to keep the text in view during typing
                const elementRect = element.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                
                // Continuous smooth scrolling to follow the text
                if (elementRect.bottom > windowHeight - 150) {
                    element.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'end',
                        inline: 'nearest' 
                    });
                }
                lastScrollTime = now;
            }
            
            i++;
            setTimeout(typeCharacter, speed);
        } else {
            // Final scroll and restore original HTML formatting
            element.innerHTML = originalHTML;
            
            // Smooth scroll to show the complete content and any choices
            setTimeout(() => {
                element.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'end',
                    inline: 'nearest' 
                });
                
                // Also scroll to show choice buttons if they exist
                const choiceButtons = document.querySelector('.choice-buttons');
                if (choiceButtons) {
                    setTimeout(() => {
                        choiceButtons.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                        });
                    }, 500);
                }
            }, 100);
            
            if (callback) callback();
        }
    }
    
    typeCharacter();
}

// Choice confirmation system
function confirmChoice(choiceNumber, choiceText) {
    // Show confirmation dialog
    const confirmed = confirm(`Confirm your choice:\n\n${choiceNumber}. ${choiceText}\n\nProceed with this action?`);
    
    if (confirmed) {
        // Set the hidden input and submit the form
        document.getElementById('selectedChoice').value = choiceNumber;
        document.getElementById('choiceForm').submit();
    }
}

// Enhanced game actions with combat system
function initializeGameActions() {
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Number keys for quick choice selection
        if (e.key >= '1' && e.key <= '3') {
            const choiceBtn = document.querySelector(`button[value="${e.key}"]`);
            if (choiceBtn && !choiceBtn.disabled) {
                choiceBtn.click();
            }
        }
        
        // Quick save/load shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 's':
                    e.preventDefault();
                    quickSave();
                    break;
                case 'l':
                    e.preventDefault();
                    quickLoad();
                    break;
                case 'm':
                    e.preventDefault();
                    useItem('medkit');
                    break;
                case 'g':
                    e.preventDefault();
                    useItem('grenade');
                    break;
                case 'c':
                    e.preventDefault();
                    const combatModal = document.getElementById('combatModal');
                    if (combatModal && combatModal.style.display === 'block') {
                        performCombatAction('attack');
                    }
                    break;
            }
        }
    });
    
    // Initialize combat system
    initializeCombatSystem();
}

// Combat System Implementation
function initializeCombatSystem() {
    // Check if combat is triggered in the story
    const storyContent = document.querySelector('#story-content, #new-content, #full-story');
    if (storyContent) {
        const story = storyContent.textContent.toLowerCase();
        const combatKeywords = ['enemy spotted', 'gunfire', 'combat', 'battle', 'firefight', 'attacked', 'ambush', 'enemy soldiers'];
        
        if (combatKeywords.some(keyword => story.includes(keyword))) {
            // Delay to allow story typing to complete
            setTimeout(() => {
                triggerCombatEncounter();
            }, 2000);
        }
    }
}

function triggerCombatEncounter() {
    // Create combat modal if it doesn't exist
    if (!document.getElementById('combatModal')) {
        createCombatModal();
    }
    
    // Start combat encounter
    showNotification('Combat encounter initiated!', 'warning');
    setTimeout(() => {
        document.getElementById('combatModal').style.display = 'block';
        initializeCombatRound();
    }, 1000);
}

function createCombatModal() {
    const modal = document.createElement('div');
    modal.id = 'combatModal';
    modal.className = 'combat-modal';
    modal.innerHTML = `
        <div class="combat-content">
            <div class="combat-header">
                <h2>⚔️ Combat Encounter</h2>
                <div class="combat-status">
                    <div class="player-status">
                        <h3>Your Status</h3>
                        <div class="health-bar">
                            <div class="health-fill" id="combatPlayerHealth"></div>
                            <span id="combatPlayerHealthText">100/100</span>
                        </div>
                    </div>
                    <div class="enemy-status">
                        <h3>Enemy Status</h3>
                        <div class="health-bar">
                            <div class="health-fill enemy-health" id="combatEnemyHealth"></div>
                            <span id="combatEnemyHealthText">100/100</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="combat-log" id="combatLog">
                <p>Enemy forces spotted! Prepare for combat!</p>
            </div>
            
            <div class="combat-actions">
                <button onclick="performCombatAction('attack')" class="combat-btn attack">🔫 Attack</button>
                <button onclick="performCombatAction('defend')" class="combat-btn defend">🛡️ Defend</button>
                <button onclick="performCombatAction('grenade')" class="combat-btn grenade">💣 Grenade</button>
                <button onclick="performCombatAction('retreat')" class="combat-btn retreat">🏃 Retreat</button>
            </div>
            
            <div class="combat-resources">
                <span>Ammo: <span id="combatAmmo">12</span></span>
                <span>Grenades: <span id="combatGrenades">2</span></span>
                <span>Medkits: <span id="combatMedkits">2</span></span>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

let combatState = {
    playerHealth: 100,
    enemyHealth: 100,
    playerAmmo: 12,
    playerGrenades: 2,
    playerMedkits: 2,
    round: 1,
    playerDefending: false
};

function initializeCombatRound() {
    // Initialize combat with player's current stats
    fetch('/get_combat_stats')
        .then(response => response.json())
        .then(data => {
            combatState.playerHealth = data.health || 100;
            combatState.playerAmmo = data.ammo || 12;
            combatState.playerGrenades = data.grenades || 2;
            combatState.playerMedkits = data.medkits || 2;
            combatState.enemyHealth = data.enemy_health || 100;
            
            updateCombatDisplay();
        })
        .catch(() => {
            // Use default values if fetch fails
            updateCombatDisplay();
        });
}

function performCombatAction(action) {
    if (combatState.enemyHealth <= 0 || combatState.playerHealth <= 0) {
        return; // Combat is over
    }
    
    let damage = 0;
    let logMessage = '';
    combatState.playerDefending = false;
    
    switch(action) {
        case 'attack':
            if (combatState.playerAmmo > 0) {
                damage = Math.floor(Math.random() * 25) + 15; // 15-40 damage
                combatState.enemyHealth -= damage;
                combatState.playerAmmo--;
                logMessage = `You fire your weapon! Enemy takes ${damage} damage.`;
            } else {
                logMessage = 'No ammo remaining! You attempt to use your rifle as a club for minimal damage.';
                damage = Math.floor(Math.random() * 10) + 5;
                combatState.enemyHealth -= damage;
            }
            break;
            
        case 'defend':
            combatState.playerDefending = true;
            logMessage = 'You take defensive position behind cover.';
            break;
            
        case 'grenade':
            if (combatState.playerGrenades > 0) {
                damage = Math.floor(Math.random() * 40) + 30; // 30-70 damage
                combatState.enemyHealth -= damage;
                combatState.playerGrenades--;
                logMessage = `Grenade explosion! Enemy takes ${damage} damage.`;
            } else {
                logMessage = 'No grenades remaining!';
            }
            break;
            
        case 'retreat':
            logMessage = 'You attempt to retreat from combat...';
            if (Math.random() < 0.7) { // 70% success rate
                endCombat('retreat');
                return;
            } else {
                logMessage += ' Retreat failed! Enemy blocks your escape.';
            }
            break;
    }
    
    addToCombatLog(logMessage);
    
    // Check if enemy is defeated
    if (combatState.enemyHealth <= 0) {
        addToCombatLog('Enemy defeated! You are victorious!');
        setTimeout(() => endCombat('victory'), 2000);
        return;
    }
    
    // Enemy turn
    setTimeout(() => {
        enemyTurn();
    }, 1500);
    
    updateCombatDisplay();
}

function enemyTurn() {
    if (combatState.enemyHealth <= 0) return;
    
    const actions = ['attack', 'heavy_attack', 'defend'];
    const action = actions[Math.floor(Math.random() * actions.length)];
    
    let damage = 0;
    let logMessage = '';
    
    switch(action) {
        case 'attack':
            damage = Math.floor(Math.random() * 20) + 10;
            if (combatState.playerDefending) {
                damage = Math.floor(damage * 0.5); // Reduced damage when defending
                logMessage = `Enemy attacks but your defense reduces the damage! You take ${damage} damage.`;
            } else {
                logMessage = `Enemy fires at you! You take ${damage} damage.`;
            }
            combatState.playerHealth -= damage;
            break;
            
        case 'heavy_attack':
            damage = Math.floor(Math.random() * 30) + 20;
            if (combatState.playerDefending) {
                damage = Math.floor(damage * 0.7);
                logMessage = `Enemy launches heavy assault! Your cover helps but you still take ${damage} damage.`;
            } else {
                logMessage = `Enemy heavy assault! You take ${damage} damage.`;
            }
            combatState.playerHealth -= damage;
            break;
            
        case 'defend':
            logMessage = 'Enemy takes defensive position.';
            break;
    }
    
    addToCombatLog(logMessage);
    
    // Check if player is defeated
    if (combatState.playerHealth <= 0) {
        addToCombatLog('You have been critically wounded!');
        setTimeout(() => endCombat('defeat'), 2000);
        return;
    }
    
    combatState.round++;
    updateCombatDisplay();
}

function addToCombatLog(message) {
    const log = document.getElementById('combatLog');
    if (log) {
        const p = document.createElement('p');
        p.textContent = `Round ${combatState.round}: ${message}`;
        log.appendChild(p);
        log.scrollTop = log.scrollHeight; // Auto-scroll combat log
    }
}

function updateCombatDisplay() {
    // Update health bars
    document.getElementById('combatPlayerHealth').style.width = Math.max(0, combatState.playerHealth) + '%';
    document.getElementById('combatPlayerHealthText').textContent = `${Math.max(0, combatState.playerHealth)}/100`;
    
    document.getElementById('combatEnemyHealth').style.width = Math.max(0, combatState.enemyHealth) + '%';
    document.getElementById('combatEnemyHealthText').textContent = `${Math.max(0, combatState.enemyHealth)}/100`;
    
    // Update resources
    document.getElementById('combatAmmo').textContent = combatState.playerAmmo;
    document.getElementById('combatGrenades').textContent = combatState.playerGrenades;
    document.getElementById('combatMedkits').textContent = combatState.playerMedkits;
    
    // Update health bar colors
    const playerHealthBar = document.getElementById('combatPlayerHealth');
    const enemyHealthBar = document.getElementById('combatEnemyHealth');
    
    updateHealthBarColor(playerHealthBar, combatState.playerHealth);
    updateHealthBarColor(enemyHealthBar, combatState.enemyHealth);
}

function updateHealthBarColor(healthBar, health) {
    healthBar.className = 'health-fill';
    if (health > 70) {
        healthBar.classList.add('health-good');
    } else if (health > 30) {
        healthBar.classList.add('health-warning');
    } else {
        healthBar.classList.add('health-danger');
    }
}

function endCombat(outcome) {
    // Send combat results to server
    fetch('/combat_result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            outcome: outcome,
            playerHealth: combatState.playerHealth,
            playerAmmo: combatState.playerAmmo,
            playerGrenades: combatState.playerGrenades,
            enemyHealth: combatState.enemyHealth,
            rounds: combatState.round
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, outcome === 'victory' ? 'success' : 'warning');
        }
    })
    .catch(error => {
        console.error('Combat result error:', error);
    });
    
    // Close combat modal
    setTimeout(() => {
        document.getElementById('combatModal').style.display = 'none';
        
        // Refresh page to update game state
        if (outcome !== 'defeat') {
            location.reload();
        } else {
            // Handle defeat - possibly redirect to game over
            setTimeout(() => {
                window.location.href = '/game_over';
            }, 2000);
        }
    }, 3000);
}

// Use item function
function useItem(itemType) {
    fetch('/use_item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `item=${itemType}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            
            // Update UI elements
            if (data.health !== undefined) {
                updateHealthDisplay(data.health);
            }
            if (data.morale !== undefined) {
                updateMoraleDisplay(data.morale);
            }
            if (data.grenades !== undefined) {
                updateResourceDisplay('grenade', data.grenades);
            }
            
            // Refresh the page to update resource counts
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        showNotification('Action failed. Try again.', 'error');
        console.error('Error:', error);
    });
}

// Quick save function
function quickSave() {
    fetch('/quick_save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
        } else {
            showNotification(data.message || 'Save failed', 'error');
        }
    })
    .catch(error => {
        showNotification('Save failed. Try again.', 'error');
        console.error('Error:', error);
    });
}

// Quick load function
function quickLoad() {
    fetch('/quick_load', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            if (data.redirect) {
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1000);
            }
        } else {
            showNotification(data.message || 'No save found', 'error');
        }
    })
    .catch(error => {
        showNotification('Load failed. Try again.', 'error');
        console.error('Error:', error);
    });
}

// Update health display
function updateHealthDisplay(health) {
    const healthFill = document.querySelector('.progress-fill');
    const healthText = document.querySelector('.progress-text');
    
    if (healthFill && healthText) {
        healthFill.style.width = health + '%';
        healthText.textContent = health + '/100';
        
        // Update health bar color
        healthFill.className = 'progress-fill';
        if (health > 70) {
            healthFill.classList.add('health-good');
        } else if (health > 30) {
            healthFill.classList.add('health-warning');
        } else {
            healthFill.classList.add('health-danger');
        }
    }
}

// Update morale display
function updateMoraleDisplay(morale) {
    const moraleFill = document.querySelector('.morale-fill');
    const moraleText = document.querySelector('.morale .progress-text');
    
    if (moraleFill && moraleText) {
        moraleFill.style.width = morale + '%';
        moraleText.textContent = morale + '%';
    }
}

// Update resource display
function updateResourceDisplay(resourceType, count) {
    const resourceElement = document.querySelector(`.${resourceType}-btn`);
    if (resourceElement) {
        const buttonText = resourceElement.innerHTML;
        const newText = buttonText.replace(/\(\d+\)/, `(${count})`);
        resourceElement.innerHTML = newText;
        
        if (count <= 0) {
            resourceElement.disabled = true;
        } else {
            resourceElement.disabled = false;
        }
    }
}

// Touch and Mobile Optimizations
function initializeTouchHandlers() {
    // Add touch feedback to all interactive elements
    const touchElements = document.querySelectorAll('.btn, .choice-btn, .mission-label');

    touchElements.forEach(element => {
        // Touch start - add pressed state
        element.addEventListener('touchstart', function(e) {
            this.classList.add('pressed');
        }, { passive: true });

        // Touch end - remove pressed state
        element.addEventListener('touchend', function(e) {
            this.classList.remove('pressed');
        }, { passive: true });

        // Touch cancel - remove pressed state
        element.addEventListener('touchcancel', function(e) {
            this.classList.remove('pressed');
        }, { passive: true });
    });

    // Prevent double-tap zoom on buttons
    const buttons = document.querySelectorAll('.btn, .choice-btn');
    buttons.forEach(button => {
        button.addEventListener('touchend', function(e) {
            e.preventDefault();
            this.click();
        });
    });
}

function initializeMobileOptimizations() {
    // Improve scrolling on mobile
    document.body.style.webkitOverflowScrolling = 'touch';

    // Prevent zoom on input focus (iOS)
    const inputs = document.querySelectorAll('input, select');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            const viewport = document.querySelector('meta[name="viewport"]');
            if (viewport) {
                viewport.setAttribute('content', 
                    'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no');
            }
        });

        input.addEventListener('blur', function() {
            const viewport = document.querySelector('meta[name="viewport"]');
            if (viewport) {
                viewport.setAttribute('content', 
                    'width=device-width, initial-scale=1.0');
            }
        });
    });

    // Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            this.classList.add('loading');
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
            }
        });
    });
}

// Notification System
function initializeNotifications() {
    window.showNotification = function(message, type = 'success', duration = 3000) {
        const notification = document.getElementById('notification');
        const text = document.getElementById('notification-text');

        if (!notification || !text) return;

        // Set message and type
        text.textContent = message;
        notification.className = `notification ${type}`;

        // Show notification
        notification.classList.add('show');
        notification.classList.remove('hidden');

        // Hide after duration
        setTimeout(() => {
            notification.classList.remove('show');
            notification.classList.add('hidden');
        }, duration);
    };
}

// Auto-save functionality
function initializeAutoSave() {
    // Save form data automatically
    const inputs = document.querySelectorAll('input, select');
    inputs.forEach(input => {
        input.addEventListener('change', function() {
            saveFormData();
        });
    });

    // Restore form data on page load
    restoreFormData();
}

function saveFormData() {
    const formData = {};
    const inputs = document.querySelectorAll('input, select');

    inputs.forEach(input => {
        if (input.type === 'radio') {
            if (input.checked) {
                formData[input.name] = input.value;
            }
        } else {
            formData[input.name] = input.value;
        }
    });

    localStorage.setItem('wwii_game_form_data', JSON.stringify(formData));
}

function restoreFormData() {
    const savedData = localStorage.getItem('wwii_game_form_data');
    if (!savedData) return;

    try {
        const formData = JSON.parse(savedData);

        Object.keys(formData).forEach(name => {
            const input = document.querySelector(`[name="${name}"]`);
            if (input) {
                if (input.type === 'radio') {
                    const radioOption = document.querySelector(`[name="${name}"][value="${formData[name]}"]`);
                    if (radioOption) {
                        radioOption.checked = true;
                    }
                } else {
                    input.value = formData[name];
                }
            }
        });
    } catch (e) {
        console.warn('Could not restore form data:', e);
    }
}

// Item Usage
function useItem(itemType) {
    fetch('/use_item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `item=${encodeURIComponent(itemType)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');

            // Update UI if health changed
            if (data.health !== undefined) {
                updateHealthDisplay(data.health);
            }

            // Reload page to reflect changes
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error using item:', error);
        showNotification('Failed to use item. Please try again.', 'error');
    });
}

function updateHealthDisplay(newHealth) {
    const healthFill = document.querySelector('.progress-fill');
    const healthText = document.querySelector('.progress-text');
    if (healthFill) {
        healthFill.style.width = `${newHealth}%`;
        healthFill.className = 'progress-fill';
        if (newHealth > 70) healthFill.classList.add('health-good');
        else if (newHealth > 30) healthFill.classList.add('health-warning');
        else healthFill.classList.add('health-danger');
    }
    if (healthText) healthText.textContent = `${newHealth}/100`;
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Only on play page with choices
    const choices = document.querySelectorAll('.choice-btn');
    if (choices.length === 0) return;

    // Number keys 1-3 for choices
    if (e.key >= '1' && e.key <= '3') {
        const choiceIndex = parseInt(e.key) - 1;
        if (choices[choiceIndex]) {
            e.preventDefault();
            choices[choiceIndex].click();
        }
    }

    // Enter key to select first choice
    if (e.key === 'Enter' && !e.target.matches('input, select, button')) {
        e.preventDefault();
        choices[0].click();
    }
});

// Typewriter Effect for Story Text
function initializeTypewriterEffect() {
    const storyContent = document.querySelector('.story-content');
    if (!storyContent) return;

    // Check if this is new content that should be typed out
    const shouldAnimate = sessionStorage.getItem('animateText') === 'true';
    if (shouldAnimate) {
        sessionStorage.removeItem('animateText');
        typewriterEffect(storyContent);
    }
}

function typewriterEffect(element) {
    const text = element.innerHTML;
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = text;
    const textContent = tempDiv.innerText || tempDiv.textContent;

    element.innerHTML = '';
    element.style.borderRight = '2px solid var(--color-primary-light)';

    let i = 0;
    const speed = 15; // Adjust typing speed (reduced for faster typing)

    function typeChar() {
        if (i < textContent.length) {
            element.innerHTML += textContent.charAt(i);
            i++;
            setTimeout(typeChar, speed);
        } else {
            element.style.borderRight = 'none';
            element.innerHTML = text; // Restore full formatting
        }
    }

    typeChar();
}

// Loading States
function initializeLoadingStates() {
    // Add loading overlay to choices
    const choiceButtons = document.querySelectorAll('.choice-btn');
    choiceButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            showLoadingOverlay();
            sessionStorage.setItem('animateText', 'true');

            // Submit the form after showing loading
            setTimeout(() => {
                this.closest('form').submit();
            }, 100);
        });
    });

    // Add loading to mission selection
    const missionForm = document.querySelector('form[action*="start_mission"]');
    if (missionForm) {
        missionForm.addEventListener('submit', function() {
            showLoadingOverlay('Deploying to mission zone...');
            sessionStorage.setItem('animateText', 'true');
        });
    }

    // Add loading to character creation
    const characterForm = document.querySelector('form[action*="create_character"]');
    if (characterForm) {
        characterForm.addEventListener('submit', function() {
            showLoadingOverlay('Enlisting soldier...');
        });
    }
}

function showLoadingOverlay(message = 'Processing tactical decision...') {
    const existingOverlay = document.querySelector('.loading-overlay'); 
    if (existingOverlay) existingOverlay.remove();

    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-content">
            <div class="loading-spinner"></div>
            <div class="loading-message">${message}</div>
            <div class="loading-dots"><span>.</span><span>.</span><span>.</span></div>
        </div>`;
    document.body.appendChild(overlay);

    setTimeout(() => { 
        if (overlay && overlay.parentNode) overlay.remove(); 
    }, 10000);
}

// Performance monitoring + SW registration
(function(){
  if ('performance' in window) {
    window.addEventListener('load', () => {
      setTimeout(() => {
        const perfData = performance.getEntriesByType('navigation')[0];
        if (perfData) console.log(`Page load: ${perfData.loadEventEnd - perfData.loadEventStart}ms`);
      }, 0);
    });
  }
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
      navigator.serviceWorker.register('/static/sw.js').then(()=>console.log('SW ok')).catch(()=>console.log('SW fail'));
    });
  }
})();

// Animation helpers
function animateElement(element, animation, duration = 500) {
    element.style.animation = `${animation} ${duration}ms ease-in-out`;

    setTimeout(() => {
        element.style.animation = '';
    }, duration);
}
