// WildBite - small vanilla JavaScript helpers

document.addEventListener('DOMContentLoaded', function () {
  // 1. Mobile menu: the ☰ button shows/hides the nav links
  var toggle = document.querySelector('.nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var isOpen = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
  }

  // 2. Alerts: the × button removes the message
  document.querySelectorAll('.alert-close').forEach(function (button) {
    button.addEventListener('click', function () {
      button.closest('.alert').remove();
    });
  });
});
