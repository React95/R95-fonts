import { Frame } from '@react95/core';
import ChangeFontModal from './ChangeFontModal';
import { NAMES } from './constants';

export const HelloModal = () => {
  return (
    <ChangeFontModal
      position={{
        x: 10,
        y: -30,
      }}
      icon={NAMES.HELLO_WORLD.icon}
      title={NAMES.HELLO_WORLD.title}
      renderContent={({ bold, fontFamily, fontSize, italic }) => {
        return (
          <Frame
            className="text"
            boxShadow="in"
            bg="white"
            p="$12"
            fontFamily={`'${fontFamily}'`}
            fontSize={`${fontSize}px`}
            fontStyle={italic ? 'italic' : 'normal'}
            fontWeight={bold ? 'bold' : 'normal'}
            mt="$20"
            as="textarea"
          >
            Hello, from R95 Sans Serif
          </Frame>
        );
      }}
    />
  );
};
