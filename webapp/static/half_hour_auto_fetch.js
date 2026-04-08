/**
 * Schedule POST /articles/auto-fetch every wall-clock :00 and :30 (local time),
 * matching server maybe_run_auto_fetch (minute 0 or 30), then re-arm indefinitely.
 */
(function () {
    function msUntilNextHalfHourPlusOneSecond() {
        const now = new Date();
        const next = new Date(now.getTime());
        next.setSeconds(0, 0);
        next.setMilliseconds(0);
        if (now.getMinutes() < 30) {
            next.setMinutes(30, 0, 0);
        } else {
            next.setHours(next.getHours() + 1);
            next.setMinutes(0, 0, 0);
        }
        return Math.max(1000, next.getTime() - now.getTime() + 1000);
    }

    /**
     * @param {() => void | Promise<void>} afterFetch - refresh UI (e.g. HTMX partial)
     */
    window.infoFeederScheduleHalfHourAutoFetch = function (afterFetch) {
        function loop() {
            window.setTimeout(async () => {
                try {
                    await fetch("/articles/auto-fetch", { method: "POST" });
                } catch (error) {
                    console.warn("auto-fetch", error);
                }
                try {
                    if (typeof afterFetch === "function") {
                        await afterFetch();
                    }
                } catch (error) {
                    console.warn("auto-fetch after", error);
                }
                loop();
            }, msUntilNextHalfHourPlusOneSecond());
        }
        loop();
    };
})();
