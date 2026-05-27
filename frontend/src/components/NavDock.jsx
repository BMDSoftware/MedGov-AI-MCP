import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { useRef } from 'react';
import './NavDock.css';

function NavDockItem({ item, isActive, mouseY, spring, distance, magnification, baseItemSize }) {
  const ref = useRef(null);

  const mouseDistance = useTransform(mouseY, val => {
    const rect = ref.current?.getBoundingClientRect() ?? { y: 0, height: baseItemSize };
    return val - rect.y - baseItemSize / 2;
  });

  const targetSize = useTransform(
    mouseDistance,
    [-distance, 0, distance],
    [baseItemSize, magnification, baseItemSize]
  );
  const size = useSpring(targetSize, spring);

  return (
    <motion.button
      ref={ref}
      style={{ height: size }}
      onClick={item.onClick}
      className={`nav-dock-item${isActive ? ' active' : ''}`}
      tabIndex={0}
    >
      <span className="nav-dock-icon">{item.icon}</span>
      <span className="nav-dock-label">{item.label}</span>
      {item.badge > 0 && (
        <span className="nav-dock-badge">{item.badge}</span>
      )}
      {item.unread && !item.badge && (
        <span className="nav-dock-badge unread">!</span>
      )}
    </motion.button>
  );
}

export default function NavDock({
  items,
  activePage,
  spring = { mass: 0.1, stiffness: 150, damping: 12 },
  magnification = 44,
  distance = 120,
  baseItemSize = 36,
}) {
  const mouseY = useMotionValue(Infinity);
  const isHovered = useMotionValue(0);

  return (
    <motion.div className="nav-dock-outer">
      <motion.div
        className="nav-dock-panel"
        onMouseMove={({ pageY }) => {
          isHovered.set(1);
          mouseY.set(pageY);
        }}
        onMouseLeave={() => {
          isHovered.set(0);
          mouseY.set(Infinity);
        }}
      >
        {items.map((item, index) =>
          item.divider ? (
            <div key={index} className="nav-dock-divider" />
          ) : (
            <NavDockItem
              key={index}
              item={item}
              isActive={activePage === item.page}
              mouseY={mouseY}
              spring={spring}
              distance={distance}
              magnification={magnification}
              baseItemSize={baseItemSize}
            />
          )
        )}
      </motion.div>
    </motion.div>
  );
}
