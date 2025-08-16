function showNote(msg) {
  const n = document.getElementById('notification');
  const t = document.getElementById('notification-text');
  if (!n || !t) return;
  t.textContent = msg;
  n.classList.remove('hidden');
  setTimeout(()=> n.classList.add('hidden'), 1500);
}

function useItem(kind) {
  showNote(`Used ${kind}. (Demo only)`);
}

function quickSave() {
  const story = document.getElementById('story-content')?.innerText || '';
  localStorage.setItem('savedStory', story);
  showNote('Quick saved.');
}

function quickLoad() {
  const txt = localStorage.getItem('savedStory') || '';
  const sc = document.getElementById('story-content');
  if (sc) sc.textContent = txt;
  showNote('Quick loaded.');
}

// Called by the choice buttons in play.html
function confirmChoice(index, text) {
  if (!confirm(`Choose ${index}: ${text}?`)) return;
  const hidden = document.getElementById('selectedChoice');
  const form = document.getElementById('choiceForm');
  if (hidden && form) {
    hidden.value = index;
    form.submit();
  }
}