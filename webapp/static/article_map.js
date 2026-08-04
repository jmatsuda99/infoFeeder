(() => {
    const mapRevision = document.body.dataset.mapRevision;
    if (mapRevision) {
        window.setInterval(async () => {
            try {
                const response = await fetch("/map/revision", { cache: "no-store" });
                const payload = await response.json();
                if (payload.revision && payload.revision !== mapRevision) {
                    window.location.reload();
                }
            } catch (error) {
                // Keep the currently rendered map if a transient local request fails.
            }
        }, 30000);
    }

    const dataElement = document.getElementById("article-map-data");
    const svg = document.getElementById("article-map");
    const detail = document.getElementById("map-detail");
    if (!dataElement || !svg || !detail) return;

    const graph = JSON.parse(dataElement.textContent);
    const canvasShell = svg.closest(".map-canvas-shell");
    const width = Math.max(1200, Math.round(canvasShell?.clientWidth || 1200));
    const height = Math.max(760, Math.round(canvasShell?.clientHeight || 760));
    const palette = ["#35658c", "#9b5f31", "#4f7d5a", "#7a5c98", "#a2465b", "#477b80"];
    const categories = [...new Set(graph.nodes.map((node) => node.category || "Uncategorized"))];
    const maxDegree = Math.max(...graph.nodes.map((node) => node.degree), 1);
    const degreeLevels = [...new Set(graph.nodes.map((node) => node.degree))].sort((left, right) => left - right);
    const sortedDegrees = graph.nodes.map((node) => node.degree).sort((left, right) => left - right);
    const hubThreshold = Math.max(3, sortedDegrees[Math.floor(sortedDegrees.length * 0.75)] || 0);
    const colourForCategory = (category) => palette[categories.indexOf(category || "Uncategorized") % palette.length];
    const escapeHtml = (value) => String(value || "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
    const radiusForDegree = (degree) => {
        if (degreeLevels.length === 1) return 15;
        // Scale by unique degree rank instead of raw degree. This preserves the
        // 5–25px range while making even small degree differences visible.
        const rank = degreeLevels.indexOf(degree);
        return 5 + 20 * (rank / (degreeLevels.length - 1));
    };
    const nodesById = new Map(graph.nodes.map((node, index) => [node.id, {
        ...node,
        radius: node.degree === maxDegree ? radiusForDegree(node.degree) : radiusForDegree(node.degree) * 0.65,
        x: width / 2 + Math.cos((index / Math.max(graph.nodes.length, 1)) * Math.PI * 2) * 180,
        y: height / 2 + Math.sin((index / Math.max(graph.nodes.length, 1)) * Math.PI * 2) * 160,
    }]));

    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const svgNs = "http://www.w3.org/2000/svg";
    const makeSvg = (tag, attributes = {}) => {
        const element = document.createElementNS(svgNs, tag);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
        svg.appendChild(element);
        return element;
    };

    const edgeElements = graph.edges.map((edge) => ({
        edge,
        element: makeSvg("line", { class: "map-edge", "stroke-width": Math.min(0.6 + edge.score * 0.15, 2) }),
    }));
    const nodeElements = [...nodesById.values()].map((node) => {
        const isHub = node.degree >= hubThreshold;
        const isTopHub = node.degree === maxDegree;
        const group = makeSvg("g", { class: `map-node${isHub ? " is-hub" : ""}${isTopHub ? " is-top-hub" : ""}`, tabindex: "0", role: "button", "aria-label": `${node.title} (${node.degree} connections)` });
        const circle = document.createElementNS(svgNs, "circle");
        // Degree is the number of strong relationships. A linear scale keeps
        // every increment visible and makes the maximum-degree hub the largest.
        circle.setAttribute("r", String(node.radius));
        circle.setAttribute("fill", isTopHub ? "#c73a3a" : colourForCategory(node.category));
        group.appendChild(circle);
        const title = document.createElementNS(svgNs, "title");
        title.textContent = `${node.title} — ${node.degree} connections`;
        group.appendChild(title);
        const label = document.createElementNS(svgNs, "text");
        label.setAttribute("y", String(node.radius + 14));
        label.textContent = node.title.length > 28 ? `${node.title.slice(0, 28)}…` : node.title;
        group.appendChild(label);
        const showDetail = () => renderDetail(node);
        group.addEventListener("click", showDetail);
        group.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") showDetail(); });
        svg.appendChild(group);
        return { node, group };
    });

    const keepInBounds = (node) => {
        node.x = Math.max(node.radius + 8, Math.min(width - node.radius - 8, node.x));
        // Reserve extra space beneath each node for its title label.
        node.y = Math.max(node.radius + 8, Math.min(height - node.radius - 30, node.y));
    };

    for (let iteration = 0; iteration < 240; iteration += 1) {
        const forces = new Map([...nodesById.values()].map((node) => [node.id, { x: 0, y: 0 }]));
        const nodes = [...nodesById.values()];
        for (let left = 0; left < nodes.length; left += 1) {
            for (let right = left + 1; right < nodes.length; right += 1) {
                const dx = nodes[right].x - nodes[left].x || 0.01;
                const dy = nodes[right].y - nodes[left].y || 0.01;
                const distance = Math.hypot(dx, dy);
                const pull = 5200 / (distance * distance);
                forces.get(nodes[left].id).x -= (dx / distance) * pull;
                forces.get(nodes[left].id).y -= (dy / distance) * pull;
                forces.get(nodes[right].id).x += (dx / distance) * pull;
                forces.get(nodes[right].id).y += (dy / distance) * pull;
            }
        }
        graph.edges.forEach((edge) => {
            const source = nodesById.get(edge.source);
            const target = nodesById.get(edge.target);
            const dx = target.x - source.x;
            const dy = target.y - source.y;
            const distance = Math.hypot(dx, dy) || 0.01;
            const pull = (distance - 135) * 0.012;
            forces.get(source.id).x += (dx / distance) * pull;
            forces.get(source.id).y += (dy / distance) * pull;
            forces.get(target.id).x -= (dx / distance) * pull;
            forces.get(target.id).y -= (dy / distance) * pull;
        });
        nodes.forEach((node) => {
            const force = forces.get(node.id);
            node.x += force.x;
            node.y += force.y;
            keepInBounds(node);
        });

        // Resolve circle collisions after applying attraction/repulsion. Run
        // several short passes so a large hub also makes room for its neighbours.
        for (let pass = 0; pass < 3; pass += 1) {
            for (let left = 0; left < nodes.length; left += 1) {
                for (let right = left + 1; right < nodes.length; right += 1) {
                    const first = nodes[left];
                    const second = nodes[right];
                    const dx = second.x - first.x || 0.01;
                    const dy = second.y - first.y || 0.01;
                    const distance = Math.hypot(dx, dy);
                    const minimumDistance = first.radius + second.radius + 8;
                    if (distance >= minimumDistance) continue;
                    const shift = (minimumDistance - distance) / 2;
                    const unitX = dx / distance;
                    const unitY = dy / distance;
                    first.x -= unitX * shift;
                    first.y -= unitY * shift;
                    second.x += unitX * shift;
                    second.y += unitY * shift;
                    keepInBounds(first);
                    keepInBounds(second);
                }
            }
        }
    }

    edgeElements.forEach(({ edge, element }) => {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        element.setAttribute("x1", source.x); element.setAttribute("y1", source.y);
        element.setAttribute("x2", target.x); element.setAttribute("y2", target.y);
    });
    nodeElements.forEach(({ node, group }) => group.setAttribute("transform", `translate(${node.x}, ${node.y})`));

    function renderDetail(node) {
        const related = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id).map((edge) => {
            const otherId = edge.source === node.id ? edge.target : edge.source;
            const other = nodesById.get(otherId);
            return `<li><button type="button" data-node-id="${other.id}">${escapeHtml(other.title)}</button><small>${escapeHtml(edge.reasons.join(" · "))}</small></li>`;
        });
        detail.innerHTML = `<p class="map-category">${escapeHtml(node.category || "Uncategorized")}</p><h2>${escapeHtml(node.title)}</h2><p class="muted">${escapeHtml(node.source_name)}${node.published_display ? ` · ${escapeHtml(node.published_display)}` : ""}</p>${node.summary ? `<p>${escapeHtml(node.summary)}</p>` : ""}${node.link ? `<p><a href="${escapeHtml(node.link)}" target="_blank" rel="noreferrer">Open article</a></p>` : ""}<h3>Connections (${related.length})</h3>${related.length ? `<ul class="map-connection-list">${related.join("")}</ul>` : "<p class=\"muted\">No strong connections yet.</p>"}`;
        detail.querySelectorAll("[data-node-id]").forEach((button) => button.addEventListener("click", () => renderDetail(nodesById.get(button.dataset.nodeId))));
    }
})();
