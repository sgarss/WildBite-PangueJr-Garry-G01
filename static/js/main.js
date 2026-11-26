document.addEventListener('DOMContentLoaded', function () {
  // Mobile menu toggle
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var isOpen = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  }

  // Disable the button after the first click so a form isn't sent twice
  document.querySelectorAll('form[data-submit-once]').forEach(function (form) {
    form.addEventListener('submit', function () {
      form.querySelectorAll('button[type="submit"]').forEach(function (button) {
        button.disabled = true;
        button.textContent = 'Please wait...';
      });
    });
  });

  // Close alerts
  document.querySelectorAll('.alert-close').forEach(function (button) {
    button.addEventListener('click', function () {
      button.closest('.alert').remove();
    });
  });
});
