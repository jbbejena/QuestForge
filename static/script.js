// WWII Text Adventure - Mobile-Optimized JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize game features
    initializeTouchHandlers();
    initializeNotifications();
    initializeAutoSave();
    initializeMobileOptimizations();
    initializeTypewriterEffect();
    initializeLoadingStates();
});

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

// Item Usage (This version will be overwritten by the enhanced version below, kept for structural fidelity)
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

// Performance monitoring
function reportPerformance() {
    if ('performance' in window) {
        window.addEventListener('load', () => {
            setTimeout(() => {
                const perfData = performance.getEntriesByType('navigation')[0];
                if (perfData) {
                    console.log(`Page load time: ${perfData.loadEventEnd - perfData.loadEventStart}ms`);
                }
            }, 0);
        });
    }
}

// Initialize performance monitoring
reportPerformance();

// Service Worker registration for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // Note: Service worker file would need to be created separately
        // This is just the registration code
        navigator.serviceWorker.register('/static/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registration successful');
            })
            .catch(function(err) {
                console.log('ServiceWorker registration failed');
            });
    });
}

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

// Loading States - FIXED: Now correctly passes button value
function initializeLoadingStates() {
    // Add loading overlay to choices
    const choiceButtons = document.querySelectorAll('.choice-btn');
    choiceButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            showLoadingOverlay();
            sessionStorage.setItem('animateText', 'true');

            const form = this.closest('form');

            // FIX: Create a hidden input to mimic the button click value
            // This ensures app.py receives "1", "2", or "3" instead of None
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'choice';
            hiddenInput.value = this.value; // Capture the value (1, 2, or 3)
            form.appendChild(hiddenInput);

            // Submit the form after showing loading
            setTimeout(() => {
                form.submit();
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

// Enhanced Item Usage with Better Error Handling
function useItem(itemType) {
    const button = event.target;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Using...';

    fetch('/use_item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `item=${encodeURIComponent(itemType)}`
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
    })
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
            button.disabled = false;
            button.innerHTML = `<i class="fas fa-first-aid"></i> Use ${itemType}`;
        }
    })
    .catch(error => {
        console.error('Error using item:', error);
        showNotification('Failed to use item. Please try again.', 'error');
        button.disabled = false;
        button.innerHTML = `<i class="fas fa-first-aid"></i> Use ${itemType}`;
    });
}

// Inject small CSS helpers
const style = document.createElement('style');
style.textContent = `
    .pressed { transform: scale(0.98) !important; opacity: 0.8 !important; transition: all 0.1s ease !important; }
    @media (prefers-reduced-motion: reduce) { .pressed { transform: none !important; } }
    .loading-overlay { position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(28,28,28,0.95); display:flex; align-items:center; justify-content:center; z-index:9999; backdrop-filter: blur(4px); }
    .loading-content { text-align:center; color: var(--color-light); max-width:300px; padding:2rem; }
    .loading-spinner { width:50px; height:50px; border:4px solid var(--color-border); border-left:4px solid var(--color-primary-light); border-radius:50%; animation: spin 1s linear infinite; margin:0 auto 1rem; }
    .loading-message { font-size:1.2rem; margin-bottom:1rem; color: var(--color-primary-light); }
    .loading-dots { font-size:2rem; color: var(--color-primary); }
    .loading-dots span { animation: blink 1.5s infinite; }
    .loading-dots span:nth-child(2) { animation-delay: 0.5s; }
    .loading-dots span:nth-child(3) { animation-delay: 1s; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes blink { 0%,50% { opacity:1; } 51%,100% { opacity:0.3; } }
    .choice-btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .story-content { min-height: 200px; }
`;
document.head.appendChild(style);