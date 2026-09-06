/* ==========================================================================
   DataNova — Landing page interactions (no dashboard/backend logic here)
   ========================================================================== */

document.addEventListener('DOMContentLoaded', function () {

    /* ---------------------------------------------------------------------
       1. Navbar: shrink + shadow on scroll
       ------------------------------------------------------------------- */
    var navbar = document.getElementById('dnNavbar');

    function handleNavbarScroll() {
        if (!navbar) return;
        if (window.scrollY > 24) {
            navbar.classList.add('dn-scrolled');
        } else {
            navbar.classList.remove('dn-scrolled');
        }
    }
    handleNavbarScroll();
    window.addEventListener('scroll', handleNavbarScroll, { passive: true });

    /* ---------------------------------------------------------------------
       2. Collapse the mobile menu after a nav link is tapped
       ------------------------------------------------------------------- */
    var navCollapseEl = document.getElementById('dnNavContent');
    var navLinks = document.querySelectorAll('.dn-nav-link');

    navLinks.forEach(function (link) {
        link.addEventListener('click', function () {
            if (navCollapseEl && navCollapseEl.classList.contains('show') && window.bootstrap) {
                try {
                    var collapseInstance = window.bootstrap.Collapse.getOrCreateInstance(navCollapseEl);
                    collapseInstance.hide();
                } catch (e) {
                    // If Bootstrap isn't fully loaded, ignore
                }
            }
        });
    });

    /* ---------------------------------------------------------------------
       3. Active navigation state on scroll (IntersectionObserver)
       ------------------------------------------------------------------- */
    var sections = document.querySelectorAll('section[id], header[id]');

    if ('IntersectionObserver' in window && sections.length) {
        var navObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    var id = entry.target.getAttribute('id');
                    navLinks.forEach(function (link) {
                        var isMatch = link.getAttribute('href') === '#' + id;
                        link.classList.toggle('active', isMatch);
                    });
                }
            });
        }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

        sections.forEach(function (section) { navObserver.observe(section); });
    }

    /* ---------------------------------------------------------------------
       4. Scroll-reveal animation for elements marked .dn-reveal
       ------------------------------------------------------------------- */
    var revealEls = document.querySelectorAll('.dn-reveal');

    if ('IntersectionObserver' in window && revealEls.length) {
        var revealObserver = new IntersectionObserver(function (entries, observer) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('dn-in-view');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });

        revealEls.forEach(function (el) { revealObserver.observe(el); });
    } else {
        // Fallback: no IntersectionObserver support — just show everything
        revealEls.forEach(function (el) { el.classList.add('dn-in-view'); });
    }

    /* ---------------------------------------------------------------------
       5. Hero mini-pipeline: cycle the active step (Upload → Clean → Analyze → Insights)
       ------------------------------------------------------------------- */
    var pipelineSteps = document.querySelectorAll('#heroPipeline .dn-pipeline-mini-step');

    if (pipelineSteps.length) {
        var activeIndex = 0;

        setInterval(function () {
            pipelineSteps[activeIndex].classList.remove('is-active');
            activeIndex = (activeIndex + 1) % pipelineSteps.length;
            pipelineSteps[activeIndex].classList.add('is-active');
        }, 1800);
    }

    /* ---------------------------------------------------------------------
       6. Back-to-top button
       ------------------------------------------------------------------- */
    var backToTopBtn = document.getElementById('dnBackToTop');

    function handleBackToTopVisibility() {
        if (!backToTopBtn) return;
        if (window.scrollY > 480) {
            backToTopBtn.classList.add('is-visible');
        } else {
            backToTopBtn.classList.remove('is-visible');
        }
    }
    handleBackToTopVisibility();
    window.addEventListener('scroll', handleBackToTopVisibility, { passive: true });

    if (backToTopBtn) {
        backToTopBtn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

});