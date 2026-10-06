// Test di carico dell'API (seduta 24). Persone che scorrono il feed dei loro stili, aprono un fit,
// votano, guardano un profilo. Ogni utente virtuale è una persona diversa (token suo).
//
//   k6 run -e USERS=$PWD/services/api/load-users.json loadtest/api.js
//   (prima: cd services/api && uv run python -m tests.load_target)
import http from "k6/http";
import { check, group, sleep } from "k6";
import { SharedArray } from "k6/data";

const BASE = __ENV.API || "http://127.0.0.1:8000";
const data = JSON.parse(open(__ENV.USERS || "../services/api/load-users.json"));
const users = new SharedArray("users", () => data.users);
const allPosts = new SharedArray("posts", () => data.posts);
const STYLES = ["old-money", "streetwear", "elegant", "minimal", "jappo", "gala"];

const VUS = Number(__ENV.VUS || 50);
// Pause tra un'azione e l'altra (1 = una persona vera; 0 = prova di stress senza pause).
const THINK = Number(__ENV.THINK ?? 1);
const pause = (s) => sleep(s * THINK);
const DURATION = __ENV.DURATION || "2m";

export const options = {
  scenarios: {
    persone: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "20s", target: VUS },
        { duration: DURATION, target: VUS },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    // Errori del server o di rete: meno dell'1%.
    http_req_failed: ["rate<0.01"],
    // Tempi (95° percentile) sopportabili su un telefono in 4G.
    "http_req_duration{name:feed}": [`p(95)<${__ENV.P95_FEED || 400}`],
    "http_req_duration{name:post}": [`p(95)<${__ENV.P95_POST || 250}`],
    "http_req_duration{name:vote}": [`p(95)<${__ENV.P95_VOTE || 300}`],
    "http_req_duration{name:user}": [`p(95)<${__ENV.P95_USER || 300}`],
    checks: ["rate>0.99"],
  },
};

function headers(token) {
  return { headers: { Authorization: `Bearer ${token}`, "X-App-Version": "0.1.0" } };
}

export default function () {
  const me = users[(__VU - 1) % users.length];
  const auth = headers(me.token);
  let picked = null;

  group("feed", () => {
    const style = STYLES[Math.floor(Math.random() * STYLES.length)];
    const res = http.get(`${BASE}/v1/feed?style=${style}`, { ...auth, tags: { name: "feed" } });
    check(res, { "feed 200": (r) => r.status === 200 });
    if (res.status === 200) {
      const items = res.json("items") || [];
      if (items.length) picked = items[Math.floor(Math.random() * items.length)];
    }
  });
  pause(1 + Math.random() * 2);

  const postId = picked ? picked.id : allPosts[Math.floor(Math.random() * allPosts.length)];
  group("fit", () => {
    const res = http.get(`${BASE}/v1/posts/${postId}`, { ...auth, tags: { name: "post" } });
    check(res, { "fit 200 o 404": (r) => r.status === 200 || r.status === 404 });
  });
  pause(0.5 + Math.random());

  if (picked && !picked.is_own && picked.vote && picked.vote.mine === null) {
    group("voto", () => {
      const res = http.put(
        `${BASE}/v1/posts/${postId}/vote`,
        JSON.stringify({ score: 40 + Math.floor(Math.random() * 61) }),
        { headers: { ...auth.headers, "Content-Type": "application/json" }, tags: { name: "vote" } },
      );
      check(res, { "voto 200": (r) => r.status === 200 });
    });
    pause(1 + Math.random() * 2);
  }

  const other = users[Math.floor(Math.random() * users.length)];
  group("profilo", () => {
    const res = http.get(`${BASE}/v1/users/${other.nickname}`, { ...auth, tags: { name: "user" } });
    check(res, { "profilo 200": (r) => r.status === 200 });
  });
  pause(1 + Math.random() * 3);
}
