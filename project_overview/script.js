(function () {
  "use strict";

  const root = document.documentElement;
  const progress = document.getElementById("progress");
  const toTop = document.getElementById("toTop");
  const nav = document.querySelector(".topbar nav");
  const menuToggle = document.getElementById("menuToggle");
  const themeToggle = document.getElementById("themeToggle");

  function updateScrollState() {
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
    progress.style.width = `${Math.min(100, ratio * 100)}%`;
    toTop.classList.toggle("visible", window.scrollY > 500);
  }

  window.addEventListener("scroll", updateScrollState, { passive: true });
  updateScrollState();

  menuToggle.addEventListener("click", function () {
    const open = nav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(open));
  });
  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () { nav.classList.remove("open"); });
  });

  const storedTheme = localStorage.getItem("sherlock-overview-theme");
  if (storedTheme === "light") root.classList.add("light");
  themeToggle.addEventListener("click", function () {
    root.classList.toggle("light");
    localStorage.setItem("sherlock-overview-theme", root.classList.contains("light") ? "light" : "dark");
  });

  toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });

  const sections = [...document.querySelectorAll("main section[id]")];
  const links = [...document.querySelectorAll(".topbar nav a")];
  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      links.forEach(function (link) { link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`); });
    });
  }, { rootMargin: "-35% 0px -55%" });
  sections.forEach(function (section) { observer.observe(section); });

  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      const name = tab.dataset.tab;
      document.querySelectorAll(".tab").forEach(function (item) { item.classList.toggle("active", item === tab); });
      document.querySelectorAll(".flow-panel").forEach(function (panel) { panel.classList.toggle("hidden", panel.dataset.panel !== name); });
    });
  });

  const counters = document.querySelectorAll("[data-count]");
  const animateCounter = function (element) {
    const target = Number(element.dataset.count);
    const duration = 900;
    const start = performance.now();
    function frame(now) {
      const progressValue = Math.min(1, (now - start) / duration);
      element.textContent = String(Math.floor(target * (1 - Math.pow(1 - progressValue, 3))));
      if (progressValue < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  };
  const counterObserver = new IntersectionObserver(function (entries, observerInstance) {
    entries.forEach(function (entry) { if (entry.isIntersecting) { animateCounter(entry.target); observerInstance.unobserve(entry.target); } });
  }, { threshold: .4 });
  counters.forEach(function (counter) { counterObserver.observe(counter); });

  const tooltip = document.getElementById("svgTooltip");
  document.querySelectorAll(".svg-node").forEach(function (node) {
    node.addEventListener("mouseenter", function (event) {
      tooltip.textContent = node.dataset.tip || "";
      tooltip.style.display = "block";
      tooltip.style.left = `${Math.min(event.offsetX + 18, node.parentElement.parentElement.clientWidth - 240)}px`;
      tooltip.style.top = `${Math.max(10, event.offsetY - 38)}px`;
    });
    node.addEventListener("mouseleave", function () { tooltip.style.display = "none"; });
  });
}());
