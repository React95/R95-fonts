import { Frame, Modal, TitleBar } from '@react95/core';
import { families } from './shared';
import { NAMES } from './constants';
import { ModalContext } from './ModalContext';
import { useContext } from 'react';

export const AllFontsModal = () => {
  const { modal, removeModal } = useContext(ModalContext);

  return (
    modal.includes(NAMES.ALL_IN_ONCE.title) && (
      <Modal
        titleBarOptions={[
          <TitleBar.Close
            key="close"
            onClick={() => {
              removeModal(NAMES.ALL_IN_ONCE.title);
            }}
          />,
        ]}
        title={NAMES.ALL_IN_ONCE.title}
        dragOptions={{
          defaultPosition: {
            x: 10,
            y: 280,
          },
        }}
        icon={NAMES.ALL_IN_ONCE.icon}
      >
        <Frame p="$3" pt="$0" maxHeight="300px" overflow="auto">
          {families.map((family) => {
            return (
              <Frame
                fontFamily={`'${family}'`}
                boxShadow="$in"
                bg="white"
                p="$12"
                fontSize="38px"
                mt="$4"
                key={family}
              >
                {family}
              </Frame>
            );
          })}
        </Frame>
      </Modal>
    )
  );
};
