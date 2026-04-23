import { AllFontsModal } from './AllFontsModal';
import { BasicLatin, SuplementLatin } from './Latin';
import { HelloModal } from './HelloModal';
import { TaskBar, List } from '@react95/core';
import { useClippy } from '@react95/clippy';
import { useContext, useEffect } from 'react';
import { NAMES } from './constants';
import { ModalContext } from './ModalContext';

const App = () => {
  const { clippy } = useClippy();
  const { addModal } = useContext(ModalContext);

  useEffect(() => {
    if (clippy) {
      clippy.play('Wave');
    }

    const speak = setTimeout(() => {
      clippy?.speak("Don't forget to star the project ⭐", false);
    }, 3000);

    const animate = setTimeout(() => {
      const animations = clippy?.animations() as string[];
      const pos = Math.abs(Math.random() * animations.length);

      clippy?.play(animations[pos]);
    }, 8000);

    return () => {
      clearTimeout(speak);
      clearTimeout(animate);
    };
  }, [clippy]);

  return (
    <>
      <TaskBar
        list={
          <List>
            {Object.entries(NAMES).map(([key, { title, iconBig }]) => {
              return (
                <List.Item
                  key={key}
                  icon={iconBig}
                  onClick={() => addModal(title)}
                >
                  {title}
                </List.Item>
              );
            })}
          </List>
        }
      />

      <HelloModal />
      <AllFontsModal />
      <SuplementLatin />
      <BasicLatin />
    </>
  );
};

export default App;
