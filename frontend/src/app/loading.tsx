"use client";

import styles from "./page.module.css";

export default function Loading() {
  return (
    <main className={styles.main}>
      <div className={styles.hero}>
        <div className={styles.glowOrb} />
        <h1 className={styles.title}>
          <span className={styles.titleAccent}>DocuFlow</span> AI
        </h1>
        <p className={styles.subtitle}>Loading...</p>
      </div>
      <div className={styles.statusGrid}>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className={styles.card}>
            <div className={styles.cardBody}>
              <div className={styles.skeleton} />
              <div className={styles.skeleton} style={{ width: "60%" }} />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
