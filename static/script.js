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
            
            // Auto-scroll every few characters to keep text visible
            const now = Date.now();
            if (now - lastScrollTime > 100) { // More frequent scrolling for better UX
                // Scroll to bottom of viewport to show new text
                const elementRect = element.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                
                // Only scroll if element is near or below viewport
                if (elementRect.bottom > windowHeight - 100) {
                    window.scrollTo({
                        top: window.scrollY + (elementRect.bottom - windowHeight + 100),
                        behavior: 'smooth'
                    });
                }
                lastScrollTime = now;
            }
            
            i++;
            setTimeout(typeCharacter, speed);
        } else {
            // Final scroll and restore original HTML formatting
            element.innerHTML = originalHTML;
            element.scrollIntoView({ behavior: 'smooth', block: 'end' });
            if (callback) callback();
        }
    }
    
    typeCharacter();
}

// Enhanced game actions
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
            }
        }
    });
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
