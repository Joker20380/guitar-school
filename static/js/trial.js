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
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (form.dataset.sending) return;
    form.dataset.sending = 'true';
    submit.disabled = true;
    form.setAttribute('aria-busy', 'true');
    const errors = form.querySelector('[data-dynamic-errors]');
    errors.hidden = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    form.querySelectorAll('[data-ajax-error]').forEach(error => error.remove());
    form.querySelectorAll('[aria-invalid]').forEach(field => field.removeAttribute('aria-invalid'));
    try {
      const response = await fetch(form.action, {
        method: 'POST', body: new FormData(form), credentials: 'same-origin', signal: controller.signal,
        headers: {'X-Requested-With': 'XMLHttpRequest'},
      });
      const result = await response.json();
      if (response.ok && result.saved === true && result.redirect) {
        window.location.assign(result.redirect);
        return;
      }
      if (!result.errors) throw new Error('Unexpected response');
      errors.replaceChildren();
      Object.entries(result.errors).forEach(([name, items]) => {
        items.forEach(item => {
          const message = document.createElement('p');
          message.textContent = item.message;
          errors.append(message);
        });
        const field = form.elements.namedItem(name);
        if (field && field.type !== 'hidden') {
          field.setAttribute('aria-invalid', 'true');
          const detail = document.createElement('div');
          detail.dataset.ajaxError = '';
          detail.id = `${field.id}_ajax_error`;
          detail.className = 'field-errors';
          detail.textContent = items.map(item => item.message).join(' ');
          field.setAttribute('aria-describedby', detail.id);
          field.after(detail);
        }
      });
    } catch (error) {
      errors.textContent = document.documentElement.lang === 'ru'
        ? 'Не удалось получить подтверждение сервера. Данные остались в форме. Попробуй ещё раз: повтор не создаст вторую заявку.'
        : 'We could not confirm the server response. Your details are still here. Try again: retrying will not create another request.';
    } finally {
      window.clearTimeout(timeout);
    }
    errors.hidden = false;
    errors.focus();
    delete form.dataset.sending;
    submit.disabled = false;
    form.removeAttribute('aria-busy');
  });
  window.addEventListener('pageshow', () => {
    delete form.dataset.sending;
    submit.disabled = false;
    form.removeAttribute('aria-busy');
  });
})();
