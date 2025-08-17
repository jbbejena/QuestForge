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
    modal.className = 'combat-modal enhanced';
    modal.innerHTML = `
        <div class="combat-content">
            <div class="combat-header">
                <h2>⚔️ Tactical Combat</h2>
                <div class="environment-indicator">
                    Environment: <span id="combatEnvironment">Open Field</span>
                </div>
            </div>
            
            <div class="combat-field">
                <div class="allied-forces">
                    <h3>Allied Forces</h3>
                    <div class="player-unit">
                        <div class="unit-name">You <span id="playerCover" class="cover-indicator"></span></div>
                        <div class="health-bar">
                            <div class="health-fill" id="combatPlayerHealth"></div>
                            <span id="combatPlayerHealthText">100/100</span>
                        </div>
                    </div>
                    <div id="squadUnits" class="squad-units"></div>
                </div>
                
                <div class="battlefield-center">
                    <div class="combat-log" id="combatLog">
                        <p>Enemy forces spotted! Tactical combat initiated!</p>
                    </div>
                </div>
                
                <div class="enemy-forces">
                    <h3>Enemy Forces</h3>
                    <div id="enemyUnits" class="enemy-units"></div>
                </div>
            </div>
            
            <div class="combat-controls">
                <div class="combat-actions">
                    <h4>Your Actions</h4>
                    <button onclick="performCombatAction('targeted_fire')" class="combat-btn attack">🎯 Targeted Fire</button>
                    <button onclick="performCombatAction('suppressing_fire')" class="combat-btn suppress">🔫 Suppressing Fire</button>
                    <button onclick="performCombatAction('take_cover')" class="combat-btn defend">🛡️ Take Cover</button>
                    <button onclick="performCombatAction('grenade')" class="combat-btn grenade">💣 Grenade</button>
                    <button onclick="performCombatAction('flank')" class="combat-btn flank">➜ Flank Enemy</button>
                    <button onclick="performCombatAction('medkit')" class="combat-btn medkit">🏥 Use Medkit</button>
                </div>
                
                <div class="squad-orders">
                    <h4>Squad Orders</h4>
                    <button onclick="squadOrder('focus_fire')" class="squad-btn">Focus Fire</button>
                    <button onclick="squadOrder('defensive')" class="squad-btn">Defensive Position</button>
                    <button onclick="squadOrder('advance')" class="squad-btn">Advance</button>
                    <button onclick="squadOrder('spread_out')" class="squad-btn">Spread Out</button>
                </div>
            </div>
            
            <div class="combat-resources">
                <span>Ammo: <span id="combatAmmo">12</span></span>
                <span>Grenades: <span id="combatGrenades">2</span></span>
                <span>Medkits: <span id="combatMedkits">2</span></span>
                <span>Round: <span id="combatRound">1</span></span>
            </div>
            
            <div class="combat-footer">
                <button onclick="attemptRetreat()" class="retreat-btn">🏃 Tactical Retreat</button>
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
    playerDefending: false,
    squadMembers: [],
    enemies: [],
    currentEnemyIndex: 0,
    combatLog: [],
    combatPaused: false,
    combatResult: null,
    playerInCover: false,
    enemiesInCover: [],
    environment: 'open_field' // open_field, urban, forest, bunker
};

function initializeCombatRound() {
    // Pause the main game
    combatState.combatPaused = true;
    
    // Initialize combat with player's current stats
    fetch('/get_combat_stats')
        .then(response => response.json())
        .then(data => {
            combatState.playerHealth = data.health || 100;
            combatState.playerAmmo = data.ammo || 12;
            combatState.playerGrenades = data.grenades || 2;
            combatState.playerMedkits = data.medkits || 2;
            
            // Initialize squad members
            combatState.squadMembers = data.squad || [];
            combatState.squadMembers = combatState.squadMembers.map(name => ({
                name: name,
                health: 80,
                maxHealth: 80,
                inCover: false,
                suppressed: false
            }));
            
            // Determine enemy count and type based on difficulty
            const difficulty = data.difficulty || 'Medium';
            const enemyCount = difficulty === 'Easy' ? 2 : difficulty === 'Hard' ? 5 : 3;
            
            // Initialize enemies
            combatState.enemies = [];
            const enemyTypes = ['Rifleman', 'Machine Gunner', 'Grenadier', 'Sniper', 'Officer'];
            for (let i = 0; i < enemyCount; i++) {
                combatState.enemies.push({
                    type: enemyTypes[Math.floor(Math.random() * enemyTypes.length)],
                    health: difficulty === 'Hard' ? 120 : 100,
                    maxHealth: difficulty === 'Hard' ? 120 : 100,
                    inCover: Math.random() > 0.5,
                    suppressed: false,
                    targeting: null
                });
            }
            
            // Set environment based on mission type
            const missionType = data.mission_type || 'patrol';
            if (missionType.includes('urban')) {
                combatState.environment = 'urban';
            } else if (missionType.includes('forest')) {
                combatState.environment = 'forest';
            } else if (missionType.includes('bunker')) {
                combatState.environment = 'bunker';
            } else {
                combatState.environment = 'open_field';
            }
            
            updateCombatDisplay();
            displayCombatUnits();
        })
        .catch(() => {
            // Use default values if fetch fails
            combatState.enemies = [
                { type: 'Rifleman', health: 100, maxHealth: 100, inCover: false, suppressed: false }
            ];
            updateCombatDisplay();
            displayCombatUnits();
        });
}

function performCombatAction(action) {
    // Check if combat is already over
    const activeEnemies = combatState.enemies.filter(e => e.health > 0);
    if (activeEnemies.length === 0 || combatState.playerHealth <= 0) {
        return;
    }
    
    let logMessage = '';
    combatState.playerDefending = false;
    
    switch(action) {
        case 'targeted_fire':
            if (combatState.playerAmmo > 0) {
                // Select enemy with lowest health or not in cover
                const target = selectBestTarget(activeEnemies);
                const hitChance = calculateHitChance(target);
                combatState.playerAmmo--;
                
                if (Math.random() < hitChance) {
                    const damage = Math.floor(Math.random() * 25) + 15;
                    target.health = Math.max(0, target.health - damage);
                    logMessage = `Targeted fire hits ${target.type}! ${damage} damage dealt.`;
                    
                    if (target.health <= 0) {
                        logMessage += ` ${target.type} eliminated!`;
                    }
                } else {
                    logMessage = `Shot missed! ${target.type} evades your fire.`;
                }
            } else {
                logMessage = 'No ammo remaining!';
            }
            break;
            
        case 'suppressing_fire':
            if (combatState.playerAmmo >= 3) {
                combatState.playerAmmo -= 3;
                let suppressed = 0;
                activeEnemies.forEach(enemy => {
                    if (Math.random() < 0.7) {
                        enemy.suppressed = true;
                        suppressed++;
                        const damage = Math.floor(Math.random() * 10) + 5;
                        enemy.health = Math.max(0, enemy.health - damage);
                    }
                });
                logMessage = `Suppressing fire! ${suppressed} enemies pinned down.`;
            } else {
                logMessage = 'Not enough ammo for suppressing fire!';
            }
            break;
            
        case 'take_cover':
            combatState.playerInCover = true;
            combatState.playerDefending = true;
            logMessage = 'You take cover behind ' + getCoverDescription();
            break;
            
        case 'grenade':
            if (combatState.playerGrenades > 0) {
                combatState.playerGrenades--;
                const targets = activeEnemies.slice(0, 2); // Hit up to 2 enemies
                let totalDamage = 0;
                targets.forEach(enemy => {
                    const damage = Math.floor(Math.random() * 40) + 30;
                    enemy.health = Math.max(0, enemy.health - damage);
                    totalDamage += damage;
                    if (enemy.inCover) enemy.inCover = false;
                });
                logMessage = `Grenade explosion! ${totalDamage} total damage to ${targets.length} enemies!`;
            } else {
                logMessage = 'No grenades remaining!';
            }
            break;
            
        case 'flank':
            if (Math.random() < 0.6) {
                combatState.playerInCover = false;
                const target = activeEnemies[0];
                target.inCover = false;
                const damage = Math.floor(Math.random() * 35) + 20;
                target.health = Math.max(0, target.health - damage);
                logMessage = `Successful flanking maneuver! ${target.type} exposed and takes ${damage} damage!`;
            } else {
                const damage = Math.floor(Math.random() * 15) + 10;
                combatState.playerHealth = Math.max(0, combatState.playerHealth - damage);
                logMessage = `Flanking attempt failed! You're exposed and take ${damage} damage!`;
            }
            break;
            
        case 'medkit':
            if (combatState.playerMedkits > 0 && combatState.playerHealth < 100) {
                combatState.playerMedkits--;
                const healAmount = 35;
                combatState.playerHealth = Math.min(100, combatState.playerHealth + healAmount);
                logMessage = `Medkit used! Restored ${healAmount} health.`;
            } else if (combatState.playerHealth >= 100) {
                logMessage = 'Already at full health!';
            } else {
                logMessage = 'No medkits available!';
            }
            break;
    }
    
    addToCombatLog(logMessage);
    
    // Squad actions
    processSquadActions();
    
    // Check victory condition
    if (activeEnemies.filter(e => e.health > 0).length === 0) {
        addToCombatLog('All enemies eliminated! Victory achieved!');
        setTimeout(() => endCombat('victory'), 2000);
        return;
    }
    
    // Enemy turn
    setTimeout(() => {
        enemyTurn();
    }, 1500);
    
    updateCombatDisplay();
}

// Helper functions for enhanced combat
function selectBestTarget(enemies) {
    // Prioritize enemies not in cover or with low health
    const exposed = enemies.filter(e => !e.inCover);
    if (exposed.length > 0) {
        return exposed.reduce((a, b) => a.health < b.health ? a : b);
    }
    return enemies.reduce((a, b) => a.health < b.health ? a : b);
}

function calculateHitChance(target) {
    let baseChance = 0.75;
    if (target.inCover) baseChance -= 0.3;
    if (target.suppressed) baseChance += 0.2;
    if (combatState.playerInCover) baseChance += 0.15;
    if (combatState.environment === 'urban') baseChance -= 0.1;
    return Math.max(0.2, Math.min(0.95, baseChance));
}

function getCoverDescription() {
    const covers = {
        'urban': ['a destroyed car', 'rubble', 'a building corner', 'a low wall'],
        'forest': ['a large tree', 'fallen logs', 'thick undergrowth', 'a rock formation'],
        'bunker': ['concrete barriers', 'sandbags', 'fortified walls', 'steel plates'],
        'open_field': ['a shallow ditch', 'tall grass', 'a small hill', 'scattered rocks']
    };
    const options = covers[combatState.environment] || covers['open_field'];
    return options[Math.floor(Math.random() * options.length)];
}

function processSquadActions() {
    if (combatState.squadMembers.length === 0) return;
    
    const activeSquad = combatState.squadMembers.filter(m => m.health > 0);
    const activeEnemies = combatState.enemies.filter(e => e.health > 0);
    
    activeSquad.forEach(member => {
        if (activeEnemies.length === 0) return;
        
        // Squad members act based on orders or autonomously
        const action = Math.random();
        if (action < 0.6) {
            // Attack
            const target = activeEnemies[Math.floor(Math.random() * activeEnemies.length)];
            const damage = Math.floor(Math.random() * 20) + 10;
            target.health = Math.max(0, target.health - damage);
            addToCombatLog(`${member.name} fires at ${target.type}, dealing ${damage} damage!`);
        } else if (action < 0.8) {
            // Support
            member.inCover = true;
            addToCombatLog(`${member.name} takes defensive position.`);
        }
    });
}

function squadOrder(order) {
    const activeSquad = combatState.squadMembers.filter(m => m.health > 0);
    let logMessage = '';
    
    switch(order) {
        case 'focus_fire':
            const target = selectBestTarget(combatState.enemies.filter(e => e.health > 0));
            if (target) {
                const totalDamage = activeSquad.length * (Math.floor(Math.random() * 15) + 10);
                target.health = Math.max(0, target.health - totalDamage);
                logMessage = `Squad focuses fire on ${target.type}! ${totalDamage} damage dealt!`;
            }
            break;
            
        case 'defensive':
            activeSquad.forEach(member => {
                member.inCover = true;
            });
            logMessage = 'Squad takes defensive positions!';
            break;
            
        case 'advance':
            activeSquad.forEach(member => {
                member.inCover = false;
            });
            combatState.enemies.forEach(enemy => {
                if (Math.random() < 0.3) enemy.suppressed = true;
            });
            logMessage = 'Squad advances aggressively!';
            break;
            
        case 'spread_out':
            const casualtyReduction = 0.5;
            combatState.squadMembers.forEach(m => m.casualtyChance = casualtyReduction);
            logMessage = 'Squad spreads out to minimize casualties!';
            break;
    }
    
    addToCombatLog(logMessage);
    updateCombatDisplay();
}

function enemyTurn() {
    const activeEnemies = combatState.enemies.filter(e => e.health > 0);
    if (activeEnemies.length === 0) return;
    
    activeEnemies.forEach(enemy => {
        // Skip if suppressed
        if (enemy.suppressed) {
            enemy.suppressed = false;
            addToCombatLog(`${enemy.type} recovers from suppression.`);
            return;
        }
        
        // Enemy AI based on type
        let action = 'attack';
        if (enemy.type === 'Sniper' && !enemy.inCover) {
            action = 'take_cover';
        } else if (enemy.type === 'Grenadier' && Math.random() < 0.3) {
            action = 'grenade';
        } else if (enemy.type === 'Officer' && Math.random() < 0.4) {
            action = 'rally';
        }
        
        switch(action) {
            case 'attack':
                // Choose target (player or squad member)
                const targets = [{ name: 'Player', health: combatState.playerHealth }];
                combatState.squadMembers.filter(m => m.health > 0).forEach(m => targets.push(m));
                const target = targets[Math.floor(Math.random() * targets.length)];
                
                let damage = Math.floor(Math.random() * 20) + 10;
                if (enemy.type === 'Machine Gunner') damage += 10;
                if (enemy.type === 'Sniper') damage += 15;
                
                // Apply cover modifiers
                if (target.name === 'Player') {
                    if (combatState.playerInCover) damage = Math.floor(damage * 0.5);
                    combatState.playerHealth = Math.max(0, combatState.playerHealth - damage);
                    addToCombatLog(`${enemy.type} shoots at you! ${damage} damage taken.`);
                } else {
                    if (target.inCover) damage = Math.floor(damage * 0.5);
                    target.health = Math.max(0, target.health - damage);
                    addToCombatLog(`${enemy.type} shoots at ${target.name}! ${damage} damage dealt.`);
                    
                    if (target.health <= 0) {
                        addToCombatLog(`${target.name} has been critically wounded!`);
                    }
                }
                break;
                
            case 'take_cover':
                enemy.inCover = true;
                addToCombatLog(`${enemy.type} takes cover.`);
                break;
                
            case 'grenade':
                const grenadeTargets = Math.random() < 0.5 ? 
                    [{ name: 'Player', health: combatState.playerHealth }] : 
                    combatState.squadMembers.filter(m => m.health > 0).slice(0, 2);
                    
                grenadeTargets.forEach(target => {
                    const damage = Math.floor(Math.random() * 25) + 15;
                    if (target.name === 'Player') {
                        combatState.playerHealth = Math.max(0, combatState.playerHealth - damage);
                    } else {
                        target.health = Math.max(0, target.health - damage);
                    }
                });
                addToCombatLog(`${enemy.type} throws a grenade! Area damage inflicted!`);
                break;
                
            case 'rally':
                activeEnemies.forEach(e => {
                    if (e.suppressed) e.suppressed = false;
                    e.health = Math.min(e.maxHealth, e.health + 10);
                });
                addToCombatLog(`${enemy.type} rallies the troops! Enemy morale boosted!`);
                break;
        }
    });
    
    // Check defeat conditions
    if (combatState.playerHealth <= 0) {
        addToCombatLog('You have been critically wounded!');
        setTimeout(() => endCombat('defeat'), 2000);
        return;
    }
    
    // Check if all squad members are down
    const activeSquad = combatState.squadMembers.filter(m => m.health > 0);
    if (combatState.squadMembers.length > 0 && activeSquad.length === 0) {
        addToCombatLog('Your entire squad has been eliminated!');
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
    // Update player health
    const playerHealthBar = document.getElementById('combatPlayerHealth');
    const playerHealthText = document.getElementById('combatPlayerHealthText');
    if (playerHealthBar) {
        playerHealthBar.style.width = Math.max(0, combatState.playerHealth) + '%';
        updateHealthBarColor(playerHealthBar, combatState.playerHealth);
    }
    if (playerHealthText) {
        playerHealthText.textContent = `${Math.max(0, combatState.playerHealth)}/100`;
    }
    
    // Update cover indicator
    const playerCover = document.getElementById('playerCover');
    if (playerCover) {
        playerCover.textContent = combatState.playerInCover ? '(In Cover)' : '';
        playerCover.className = combatState.playerInCover ? 'cover-indicator in-cover' : 'cover-indicator';
    }
    
    // Update resources
    document.getElementById('combatAmmo').textContent = combatState.playerAmmo;
    document.getElementById('combatGrenades').textContent = combatState.playerGrenades;
    document.getElementById('combatMedkits').textContent = combatState.playerMedkits;
    document.getElementById('combatRound').textContent = combatState.round;
    
    // Update environment
    const envElement = document.getElementById('combatEnvironment');
    if (envElement) {
        const envNames = {
            'urban': 'Urban Warfare',
            'forest': 'Forest Combat',
            'bunker': 'Bunker Assault',
            'open_field': 'Open Field'
        };
        envElement.textContent = envNames[combatState.environment] || 'Unknown';
    }
    
    displayCombatUnits();
}

function displayCombatUnits() {
    // Display squad units
    const squadContainer = document.getElementById('squadUnits');
    if (squadContainer) {
        squadContainer.innerHTML = '';
        combatState.squadMembers.forEach(member => {
            const unitDiv = document.createElement('div');
            unitDiv.className = 'squad-unit' + (member.health <= 0 ? ' wounded' : '');
            unitDiv.innerHTML = `
                <div class="unit-name">${member.name} ${member.inCover ? '<span class="cover-indicator">(Cover)</span>' : ''}</div>
                <div class="health-bar small">
                    <div class="health-fill" style="width: ${(member.health / member.maxHealth) * 100}%"></div>
                    <span class="health-text">${member.health}/${member.maxHealth}</span>
                </div>
            `;
            squadContainer.appendChild(unitDiv);
        });
    }
    
    // Display enemy units
    const enemyContainer = document.getElementById('enemyUnits');
    if (enemyContainer) {
        enemyContainer.innerHTML = '';
        combatState.enemies.forEach((enemy, index) => {
            const unitDiv = document.createElement('div');
            unitDiv.className = 'enemy-unit' + (enemy.health <= 0 ? ' eliminated' : '');
            unitDiv.innerHTML = `
                <div class="unit-name">
                    ${enemy.type} 
                    ${enemy.inCover ? '<span class="cover-indicator">(Cover)</span>' : ''}
                    ${enemy.suppressed ? '<span class="suppressed">(Suppressed)</span>' : ''}
                </div>
                <div class="health-bar small enemy-health">
                    <div class="health-fill" style="width: ${(enemy.health / enemy.maxHealth) * 100}%"></div>
                    <span class="health-text">${enemy.health}/${enemy.maxHealth}</span>
                </div>
            `;
            enemyContainer.appendChild(unitDiv);
        });
    }
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
    combatState.combatResult = outcome;
    combatState.combatPaused = false;
    
    // Prepare combat summary
    const enemiesEliminated = combatState.enemies.filter(e => e.health <= 0).length;
    const squadCasualties = combatState.squadMembers.filter(m => m.health <= 0).map(m => m.name);
    const roundsSurvived = combatState.round;
    
    // Send enhanced combat results to server
    fetch('/integrate_combat_result', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            outcome: outcome,
            playerHealth: combatState.playerHealth,
            playerAmmo: combatState.playerAmmo,
            playerGrenades: combatState.playerGrenades,
            playerMedkits: combatState.playerMedkits,
            enemiesEliminated: enemiesEliminated,
            totalEnemies: combatState.enemies.length,
            squadCasualties: squadCasualties,
            rounds: roundsSurvived,
            environment: combatState.environment
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
    
    // Close combat modal and integrate results into story
    setTimeout(() => {
        const modal = document.getElementById('combatModal');
        if (modal) {
            modal.style.display = 'none';
        }
        
        // Refresh page to show updated story with combat results
        if (outcome !== 'defeat') {
            location.reload();
        } else {
            // Handle defeat
            setTimeout(() => {
                window.location.href = '/game_over';
            }, 2000);
        }
    }, 3000);
}

function attemptRetreat() {
    const activeSquad = combatState.squadMembers.filter(m => m.health > 0);
    const retreatChance = 0.5 + (activeSquad.length * 0.1);
    
    if (Math.random() < retreatChance) {
        addToCombatLog('Tactical retreat successful! Falling back to safer position.');
        endCombat('retreat');
    } else {
        const damage = Math.floor(Math.random() * 20) + 10;
        combatState.playerHealth = Math.max(0, combatState.playerHealth - damage);
        addToCombatLog(`Retreat blocked by enemy fire! You take ${damage} damage.`);
        
        if (combatState.playerHealth <= 0) {
            endCombat('defeat');
        } else {
            updateCombatDisplay();
            enemyTurn();
        }
    }
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
