async function sendVoiceMonkeyAnnouncement(env, speechText) {
  if (!env.VOICEMONKEY_TOKEN || !env.VOICEMONKEY_DEVICE) {
    console.warn("VoiceMonkey token or device not configured.");
    return { configured: false };
  }
  try {
    const res = await fetch("https://api-v3.voicemonkey.io/announce", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.VOICEMONKEY_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token: env.VOICEMONKEY_TOKEN,
        device: env.VOICEMONKEY_DEVICE,
        speech: speechText,
      }),
    });
    return { configured: true, status: res.status, ok: res.ok };
  } catch (err) {
    console.error(`VoiceMonkey fetch error: ${err.message}`);
    return { configured: true, error: err.message };
  }
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST" && request.method !== "GET") {
      return new Response("Method Not Allowed. Send POST or GET.", { status: 405 });
    }

    try {
      const trmnlKey = env.TRMNL_DEVICE_API_KEY;
      const pluginId = env.TRMNL_PLUGIN_ID;
      const eventType = env.EVENT_TYPE || "flic_water_all_dev";

      console.log(`Processing Flic trigger for event: ${eventType}`);

      // 1. Query TRMNL current display API (Checks active screen in ~100ms)
      let filename = "";
      if (trmnlKey) {
        try {
          const trmnlRes = await fetch("https://trmnl.com/api/display/current", {
            headers: { "access-token": trmnlKey },
          });

          if (trmnlRes.ok) {
            const data = await trmnlRes.json();
            filename = (data.filename || data.image_name || "").toLowerCase();
            console.log(`Active TRMNL screen: ${filename}`);
          } else {
            console.warn(`Could not fetch TRMNL screen state: HTTP ${trmnlRes.status}`);
          }
        } catch (trmnlErr) {
          console.error(`Error querying TRMNL API: ${trmnlErr.message}`);
        }
      }

      // 2. Verify screen context
      let isMatch = false;
      if (!trmnlKey) {
        isMatch = true;
      } else if (pluginId) {
        isMatch = filename.includes(pluginId.toLowerCase());
      } else {
        isMatch = filename.includes("plugin-") || filename.includes("custom-") || filename.includes("water");
      }

      if (!isMatch) {
        console.log(`Screen check failed. Active screen '${filename}' did not match plugin ID '${pluginId}'.`);

        // Announce immediately via VoiceMonkey with Bearer authorization and abort!
        const vmResult = await sendVoiceMonkeyAnnouncement(
          env,
          "Oops! Looks like the plant dashboard isn't on your screen. Try it when it is ON"
        );

        return new Response(
          JSON.stringify({
            status: "ignored",
            reason: "wrong_screen",
            active_screen: filename,
            expected_plugin: pluginId,
            voicemonkey: vmResult,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }

      // 3. SCREEN VERIFIED!
      console.log("Screen context verified successfully.");

      // A. Instant VoiceMonkey confirmation (<1 second) with Bearer authorization
      const vmResult = await sendVoiceMonkeyAnnouncement(
        env,
        "Working on watering your plants now, this might take a bit of time"
      );

      // B. Dispatch GitHub Actions to perform Airtable updates & TRMNL refresh
      const ghRepo = env.GITHUB_REPO || "damiththa/water-me-please";
      const ghRes = await fetch(`https://api.github.com/repos/${ghRepo}/dispatches`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_PAT}`,
          "Accept": "application/vnd.github+json",
          "User-Agent": "Cloudflare-Worker-Flic-Proxy",
        },
        body: JSON.stringify({ event_type: eventType }),
      });

      console.log(`GitHub Action dispatch status: ${ghRes.status}`);

      return new Response(
        JSON.stringify({
          status: "dispatched",
          event_type: eventType,
          github_dispatch_status: ghRes.status,
          voicemonkey: vmResult,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    } catch (err) {
      console.error(`Worker error: ${err.message}`);
      return new Response(
        JSON.stringify({ error: err.message }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
  },
};
