const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('#navigation');
toggle?.setAttribute('data-ready', 'true');
function closeMenu() { toggle?.setAttribute('aria-expanded', 'false'); nav?.classList.remove('is-open'); }
toggle?.addEventListener('click', () => { const open = toggle.getAttribute('aria-expanded') !== 'true'; toggle.setAttribute('aria-expanded', String(open)); nav.classList.toggle('is-open', open); });
nav?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
document.addEventListener('click', event => { if (!event.target.closest('.site-header')) closeMenu(); });
