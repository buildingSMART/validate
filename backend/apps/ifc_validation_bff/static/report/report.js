document.addEventListener('click', async (event) => {
  const button = event.target.closest('.copy');
  if (!button) return;
  event.preventDefault();
  const text = button.closest('details').querySelector('.clipboard').value;
  try {
    await navigator.clipboard.writeText(text);
    button.title = 'Copied!';
  } catch {
    button.title = 'Copy failed';
  }
});
