(() => {
    const header = document.getElementById("sticky-header");
    const mobileToggle = document.querySelector("[data-mobile-toggle]");
    const mobileNav = document.querySelector("[data-mobile-nav]");
    const scrollTopButton = document.querySelector("[data-scroll-top]");

    function syncHeader() {
        const isSticky = window.scrollY > 80;

        if (header) {
            header.classList.toggle("sticky", isSticky);
        }

        if (scrollTopButton) {
            scrollTopButton.classList.toggle("visible", window.scrollY > 500);
        }
    }

    function closeMobileMenu() {
        if (!mobileToggle || !mobileNav) {
            return;
        }

        mobileToggle.classList.remove("active");
        mobileNav.classList.remove("active");
        document.body.classList.remove("menu-open");
    }

    function initMobileMenu() {
        if (!mobileToggle || !mobileNav) {
            return;
        }

        mobileToggle.addEventListener("click", () => {
            mobileToggle.classList.toggle("active");
            mobileNav.classList.toggle("active");
            document.body.classList.toggle("menu-open");
        });

        mobileNav.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", closeMobileMenu);
        });

        window.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeMobileMenu();
            }
        });
    }

    function initSmoothAnchors() {
        document.querySelectorAll('a[href^="#"]').forEach((link) => {
            link.addEventListener("click", (event) => {
                const href = link.getAttribute("href");

                if (!href || href === "#") {
                    return;
                }

                const target = document.querySelector(href);

                if (!target) {
                    return;
                }

                event.preventDefault();
                closeMobileMenu();

                const headerOffset = header ? header.offsetHeight + 16 : 0;
                const targetTop = target.getBoundingClientRect().top + window.scrollY - headerOffset;

                window.scrollTo({
                    top: targetTop,
                    behavior: "smooth",
                });
            });
        });
    }

    function initReveal() {
        const items = document.querySelectorAll(".reveal");

        if (!items.length) {
            return;
        }

        if (!("IntersectionObserver" in window)) {
            items.forEach((item) => item.classList.add("visible"));
            return;
        }

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }

                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            });
        }, {
            threshold: 0.14,
        });

        items.forEach((item) => observer.observe(item));
    }

    function initScrollTop() {
        if (!scrollTopButton) {
            return;
        }

        scrollTopButton.addEventListener("click", () => {
            window.scrollTo({
                top: 0,
                behavior: "smooth",
            });
        });
    }

    function initActiveNav() {
        const currentPath = window.location.pathname;

        document.querySelectorAll(".desktop-nav a, .mobile-nav a").forEach((link) => {
            const href = link.getAttribute("href");

            if (!href || href.startsWith("#")) {
                return;
            }

            if (href === currentPath || (href !== "/" && currentPath.startsWith(href))) {
                link.classList.add("active");
            }
        });
    }

    window.addEventListener("scroll", syncHeader, { passive: true });
    window.addEventListener("resize", syncHeader);

    document.addEventListener("DOMContentLoaded", () => {
        syncHeader();
        initMobileMenu();
        initSmoothAnchors();
        initReveal();
        initScrollTop();
        initActiveNav();
    });
})();
