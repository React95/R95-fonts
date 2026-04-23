import { TextArea } from '@react95/core';
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
          <TextArea
            className="text"
            boxShadow="in"
            bg="white"
            p="$12"
            fontFamily={`'${fontFamily}'`}
            fontSize={`${fontSize}px`}
            fontStyle={italic ? 'italic' : 'normal'}
            fontWeight={bold ? 'bold' : 'normal'}
            m="$3"
            mt="$20"
            as="textarea"
            defaultValue="Hello, from R95 Fonts"
          />
        );
      }}
    />
  );
};
