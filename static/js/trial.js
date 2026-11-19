(() => {
  const form = document.querySelector('[data-trial-form]');
  if (!form) return;
  const channel = form.querySelector('[name="preferred_contact"]');
  const submit = form.querySelector('[data-submit]');
  const updateFields = () => {
    form.querySelectorAll('[data-contact-field]').forEach(group => {
      const applicable = group.dataset.contactField === channel.value;
      group.hidden = !applicable;
      group.querySelectorAll('input').forEach(input => { input.disabled = !applicable; });
    });
  };
  channel.addEventListener('change', updateFields);
  updateFields();
  const phone = form.querySelector('[name="phone"]');
  phone.setAttribute('aria-describedby', [phone.getAttribute('aria-describedby'), 'phone-help'].filter(Boolean).join(' '));
  form.querySelectorAll('.field-errors').forEach(error => {
    const input = error.parentElement.querySelector('input, select');
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', error.id);
  });
  document.querySelector('[data-error-summary]')?.focus();
  form.addEventListener('submit', event => {
    if (form.dataset.sending) { event.preventDefault(); return; }
    form.dataset.sending = 'true';
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    delete form.dataset.sending;
    submit.disabled = false;
    form.removeAttribute('aria-busy');
  });
})();
